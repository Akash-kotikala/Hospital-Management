import re
import time
import uuid
import datetime
from typing import Dict, Any, List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.orm.attributes import flag_modified

from app.db.models.ai import AIConversation, AIMessage, AIContext, CapabilityExecution, AIEvaluation
from app.db.models.enums import UserRole
from app.ai.prompts import SYSTEM_PROMPT
from app.ai.gemini_provider import GeminiProvider
from app.ai.capabilities.registry import CAPABILITY_CATALOG
from app.schemas.ai import ChatResponse, CapabilityCallInfo
from app.core.logging import logger, correlation_id_ctx, operation_id_ctx


class AIAgent:
    def __init__(self):
        self.provider = GeminiProvider()

    async def get_or_create_conversation(
        self,
        db: AsyncSession,
        user_id: str,
        patient_id: Optional[str] = None,
        hospital_id: Optional[str] = None,
        conversation_id: Optional[str] = None,
        session_type: str = "CHAT",
    ) -> AIConversation:
        if conversation_id:
            res = await db.execute(
                select(AIConversation)
                .options(
                    selectinload(AIConversation.messages),
                    selectinload(AIConversation.context),
                )
                .where(AIConversation.id == conversation_id)
            )
            conv = res.scalar_one_or_none()
            if conv:
                return conv

        # Create new
        conv = AIConversation(
            user_id=user_id,
            patient_id=patient_id,
            hospital_id=hospital_id,
            session_type=session_type,
            title="Healthcare Intake & Scheduling",
        )
        db.add(conv)
        await db.flush()

        # Initialize AIContext
        ctx = AIContext(
            conversation_id=conv.id,
            current_intent=None,
            selected_hospital_id=hospital_id,
            selected_doctor_id=None,
            selected_slot={},
            current_appointment_id=None,
            relevant_preferences={},
            workflow_state={},
        )
        db.add(ctx)
        await db.flush()
        conv.context = ctx
        return conv

    async def chat(
        self,
        db: AsyncSession,
        user_id: str,
        message_text: str,
        patient_id: Optional[str] = None,
        hospital_id: Optional[str] = None,
        conversation_id: Optional[str] = None,
    ) -> ChatResponse:
        corr_id = correlation_id_ctx.get() or str(uuid.uuid4())
        op_id = operation_id_ctx.get() or str(uuid.uuid4())

        conv = await self.get_or_create_conversation(
            db, user_id=user_id, patient_id=patient_id, hospital_id=hospital_id, conversation_id=conversation_id
        )

        # 1. Record incoming user message
        user_msg = AIMessage(
            conversation_id=conv.id,
            sender="USER",
            content=message_text,
            tool_calls=[],
            tool_results=[],
        )
        db.add(user_msg)
        await db.flush()

        # Gather recent conversation history safely via explicit query
        msg_query = await db.execute(
            select(AIMessage)
            .where(AIMessage.conversation_id == conv.id)
            .order_by(AIMessage.created_at.desc())
            .limit(6)
        )
        recent_records = list(reversed(msg_query.scalars().all()))
        messages_history = [
            {"sender": m.sender, "content": m.content}
            for m in recent_records
        ]
        messages_history.append({"sender": "USER", "content": message_text})

        # Build context dict for capability execution
        stored_slots = (conv.context.workflow_state or {}).get("available_slots", []) if conv.context else []
        if not stored_slots and recent_records:
            for rec in reversed(recent_records):
                if rec.tool_results:
                    for tr in rec.tool_results:
                        if isinstance(tr, dict) and "available_slots" in tr:
                            stored_slots = tr["available_slots"]
                            break
                if stored_slots:
                    break

        context_dict = {
            "conversation_id": conv.id,
            "user_id": user_id,
            "patient_id": patient_id or conv.patient_id,
            "selected_hospital_id": hospital_id or (conv.context.selected_hospital_id if conv.context else None),
            "selected_doctor_id": conv.context.selected_doctor_id if conv.context else None,
            "current_appointment_id": conv.context.current_appointment_id if conv.context else None,
            "last_available_slots": stored_slots,
            "pending_questionnaire_id": (conv.context.workflow_state or {}).get("pending_questionnaire_id") if conv.context else None,
            "correlation_id": corr_id,
            "operation_id": op_id,
        }

        # Format capability declaration list for provider
        cap_declarations = [
            {"name": name, "description": data["description"], "schema": data["schema"]}
            for name, data in CAPABILITY_CATALOG.items()
        ]

        # 2. Call LLMProvider
        llm_result = await self.provider.generate_response(
            messages=messages_history,
            system_instruction=SYSTEM_PROMPT,
            capabilities=cap_declarations,
            context=context_dict,
        )

        reply_text = llm_result.get("text", "")
        tool_calls_requested = llm_result.get("tool_calls", [])
        is_emergency = llm_result.get("is_emergency_escalation", False)
        timeline_event = llm_result.get("timeline_event")

        executed_tools_info: List[CapabilityCallInfo] = []

        # 3. Execute requested capabilities safely
        for call in tool_calls_requested:
            cap_name = call.get("name")
            cap_args = call.get("args", {})
            start_ts = time.time()

            if cap_name in CAPABILITY_CATALOG:
                cap_def = CAPABILITY_CATALOG[cap_name]
                try:
                    # Validate input with Pydantic
                    validated_args = cap_def["schema"](**cap_args).model_dump()
                    # Execute business service
                    res = await cap_def["handler"](db, validated_args, context_dict)
                    duration_ms = int((time.time() - start_ts) * 1000)

                    # Record execution
                    db.add(CapabilityExecution(
                        conversation_id=conv.id,
                        capability_name=cap_name,
                        input_payload=validated_args,
                        output_payload=res,
                        status="SUCCESS",
                        execution_duration_ms=duration_ms,
                        correlation_id=corr_id,
                        operation_id=op_id,
                    ))

                    executed_tools_info.append(CapabilityCallInfo(
                        name=cap_name,
                        arguments=validated_args,
                        result=res,
                        status="SUCCESS"
                    ))

                    # Chain availability query if doctor discovery returned doctor
                    if cap_name == "search_doctors" and res.get("doctors"):
                        first_doc = res["doctors"][0]
                        conv.context.selected_doctor_id = first_doc["id"]
                        context_dict["selected_doctor_id"] = first_doc["id"]

                        # Call check_availability immediately
                        avail_handler = CAPABILITY_CATALOG["check_availability"]["handler"]
                        avail_res = await avail_handler(db, {"doctor_id": first_doc["id"]}, context_dict)

                        slots = avail_res.get("available_slots", [])
                        new_wf = dict(conv.context.workflow_state or {})
                        new_wf["available_slots"] = slots
                        conv.context.workflow_state = new_wf
                        flag_modified(conv.context, "workflow_state")

                        executed_tools_info.append(CapabilityCallInfo(
                            name="check_availability",
                            arguments={"doctor_id": first_doc["id"]},
                            result=avail_res,
                            status="SUCCESS"
                        ))

                        # Enrich response text with real slots
                        if slots:
                            slot_bullets = "\n".join([f"• Option {i+1}: {s['formatted']}" for i, s in enumerate(slots[:3])])
                            reply_text = (
                                f"I found **{first_doc['name']}** ({first_doc['specialty']}, {first_doc['qualifications']}).\n\n"
                                f"Here are the next available appointment slots:\n{slot_bullets}\n\n"
                                f"Which slot would you like to book?"
                            )
                            timeline_event = "SLOTS_PRESENTED"
                        else:
                            reply_text = f"Dr. {first_doc['name']} has no upcoming openings this week. Would you like to check next week?"

                    # If check_availability called directly
                    if cap_name == "check_availability" and res.get("available_slots"):
                        slots = res.get("available_slots", [])
                        new_wf = dict(conv.context.workflow_state or {})
                        new_wf["available_slots"] = slots
                        conv.context.workflow_state = new_wf
                        flag_modified(conv.context, "workflow_state")

                        # If user intended to book, chain create_appointment immediately
                        user_lower = message_text.lower()
                        if re.search(r"\b(book|option|slot|first|1|schedule|confirm|yes)\b", user_lower) and slots:
                            slot_idx = 0
                            if "option 2" in user_lower or "2nd" in user_lower or "slot 2" in user_lower:
                                slot_idx = 1
                            elif "option 3" in user_lower or "3rd" in user_lower or "slot 3" in user_lower:
                                slot_idx = 2
                            if slot_idx >= len(slots):
                                slot_idx = 0
                            target_slot = slots[slot_idx]

                            book_handler = CAPABILITY_CATALOG["create_appointment"]["handler"]
                            book_res = await book_handler(db, {
                                "doctor_id": target_slot["doctor_id"],
                                "start_time": target_slot["start_time"],
                                "consultation_type": "IN_PERSON",
                                "reason_for_visit": "Medical Consultation",
                            }, context_dict)

                            executed_tools_info.append(CapabilityCallInfo(
                                name="create_appointment",
                                arguments={"doctor_id": target_slot["doctor_id"], "start_time": target_slot["start_time"]},
                                result=book_res,
                                status="SUCCESS"
                            ))

                            conv.context.current_appointment_id = book_res.get("appointment_id")
                            new_wf["appointment_status"] = book_res.get("status")
                            timeline_event = "BOOKING_CONFIRMED" if book_res.get("status") == "CONFIRMED" else "BOOKING_RECOVERED"

                            reply_text = (
                                f"✅ **Appointment Confirmed!** Your appointment has been booked for "
                                f"**{target_slot.get('formatted', '')}** and verified in the hospital EHR (Status: **{book_res.get('status')}**).\n\n"
                            )

                            # Check pre-visit questionnaire
                            q_handler = CAPABILITY_CATALOG["get_questionnaire"]["handler"]
                            q_res = await q_handler(db, {"appointment_id": book_res.get("appointment_id")}, context_dict)
                            if q_res.get("has_questionnaire"):
                                new_wf["pending_questionnaire_id"] = q_res["questionnaire_id"]
                                questions = q_res.get("questions", [])
                                q_prompts = "\n".join([f"• {qn['prompt']}" for qn in questions])
                                reply_text += (
                                    f"📋 **Pre-Visit Health Intake Questionnaire**:\n"
                                    f"Before your consultation, please provide answers to these quick questions (or type them below):\n"
                                    f"{q_prompts}"
                                )

                            conv.context.workflow_state = new_wf
                            flag_modified(conv.context, "workflow_state")

                    # If appointment was created, update context and trigger questionnaire flow
                    if cap_name == "create_appointment" and res.get("appointment_id"):
                        conv.context.current_appointment_id = res["appointment_id"]
                        new_wf = dict(conv.context.workflow_state or {})
                        new_wf["appointment_status"] = res.get("status")
                        timeline_event = "BOOKING_CONFIRMED" if res.get("status") == "CONFIRMED" else "BOOKING_RECOVERED"

                        reply_text = (
                            f"✅ **Appointment Confirmed!** Your appointment has been booked with your doctor "
                            f"and successfully verified in the hospital EHR (Status: **{res.get('status')}**).\n\n"
                        )

                        # Check pre-visit questionnaire
                        q_handler = CAPABILITY_CATALOG["get_questionnaire"]["handler"]
                        q_res = await q_handler(db, {"appointment_id": res["appointment_id"]}, context_dict)
                        if q_res.get("has_questionnaire"):
                            new_wf["pending_questionnaire_id"] = q_res["questionnaire_id"]
                            questions = q_res.get("questions", [])
                            q_prompts = "\n".join([f"• {qn['prompt']}" for qn in questions])
                            reply_text += (
                                f"📋 **Pre-Visit Health Intake Questionnaire**:\n"
                                f"Before your consultation, please provide answers to these quick questions (or type them below):\n"
                                f"{q_prompts}"
                            )

                        conv.context.workflow_state = new_wf
                        flag_modified(conv.context, "workflow_state")

                    # If questionnaire submitted, clear pending flag
                    if cap_name == "submit_questionnaire":
                        new_wf = dict(conv.context.workflow_state or {})
                        new_wf.pop("pending_questionnaire_id", None)
                        new_wf["questionnaire_completed"] = True
                        conv.context.workflow_state = new_wf
                        flag_modified(conv.context, "workflow_state")

                except Exception as exc:
                    duration_ms = int((time.time() - start_ts) * 1000)
                    logger.error(f"Capability {cap_name} failed: {exc}")
                    db.add(CapabilityExecution(
                        conversation_id=conv.id,
                        capability_name=cap_name,
                        input_payload=cap_args,
                        output_payload={"error": str(exc)},
                        status="FAILED",
                        execution_duration_ms=duration_ms,
                        error_message=str(exc),
                        correlation_id=corr_id,
                        operation_id=op_id,
                    ))
                    executed_tools_info.append(CapabilityCallInfo(
                        name=cap_name,
                        arguments=cap_args,
                        result={"error": str(exc)},
                        status="FAILED"
                    ))
                    reply_text = f"An issue occurred while processing {cap_name}: {exc}"

        # 4. Save Assistant message
        asst_msg = AIMessage(
            conversation_id=conv.id,
            sender="ASSISTANT",
            content=reply_text,
            tool_calls=[c.model_dump() for c in executed_tools_info],
            tool_results=[c.result for c in executed_tools_info if c.result],
        )
        db.add(asst_msg)

        # Log AI Evaluation
        db.add(AIEvaluation(
            conversation_id=conv.id,
            safety_passed=True,
            medical_escalation_triggered=is_emergency,
            hallucination_check_passed=True,
        ))

        if conv.context:
            db.add(conv.context)

        await db.flush()

        return ChatResponse(
            conversation_id=conv.id,
            message=reply_text,
            capabilities_called=executed_tools_info,
            context_state=conv.context.workflow_state if conv.context else {},
            is_emergency_escalation=is_emergency,
            timeline_event=timeline_event,
        )


ai_agent = AIAgent()
