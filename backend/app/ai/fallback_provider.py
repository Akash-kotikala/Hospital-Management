import re
import datetime
from typing import Dict, Any, List, Optional
from app.ai.provider import LLMProvider
from app.ai.prompts import EMERGENCY_KEYWORDS
from app.core.logging import logger


class FallbackProvider(LLMProvider):
    """
    Deterministic administrative rule-based provider for offline testing,
    environments without GEMINI_API_KEY, and fallback scenarios.
    Interacts strictly through controlled capabilities.
    """

    async def generate_response(
        self,
        messages: List[Dict[str, Any]],
        system_instruction: str,
        capabilities: List[Dict[str, Any]],
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        latest_user_msg = ""
        for m in reversed(messages):
            if m.get("role") == "user" or m.get("sender") == "USER":
                latest_user_msg = (m.get("content") or "").strip()
                break

        user_lower = latest_user_msg.lower()

        # 1. Safety Check: Emergency detection
        for kw in EMERGENCY_KEYWORDS:
            if kw in user_lower:
                return {
                    "text": (
                        "CRITICAL EMERGENCY ALERT: You have mentioned acute symptoms that may indicate a life-threatening emergency. "
                        "Please IMMEDIATELY call 911 (or your local emergency services) or have someone take you to the nearest emergency room. "
                        "As an administrative scheduling assistant, I cannot provide medical evaluation or emergency care."
                    ),
                    "tool_calls": [],
                    "is_emergency_escalation": True,
                    "timeline_event": "EMERGENCY_ESCALATION",
                }

        # 2. Intent: Pre-Visit Questionnaire completion
        if context.get("pending_questionnaire_id") or "questionnaire" in user_lower or context.get("questionnaire_in_progress"):
            # If user provides answers
            appt_id = context.get("current_appointment_id")
            if appt_id:
                return {
                    "text": "Thank you for providing your responses. I have recorded your pre-visit health questionnaire answers. Your doctor has been notified and will review them prior to your consultation.",
                    "tool_calls": [
                        {
                            "name": "submit_questionnaire",
                            "args": {
                                "appointment_id": appt_id,
                                "answers": {"patient_notes": latest_user_msg, "intake_confirmed": True},
                            }
                        }
                    ],
                    "timeline_event": "QUESTIONNAIRE_COMPLETED",
                }

        # 3. Intent: Slot Selection / Booking confirmation
        selected_slot = None
        available_slots = context.get("last_available_slots", [])
        
        # Check if user selected slot by index, day name, or keyword
        if available_slots:
            slot_idx = None
            if re.search(r"\b(first|1st|1|option 1|opt 1|slot 1|first available|first slot)\b", user_lower):
                slot_idx = 0
            elif re.search(r"\b(second|2nd|2|option 2|opt 2|slot 2|second available|second slot)\b", user_lower):
                slot_idx = 1
            elif re.search(r"\b(third|3rd|3|option 3|opt 3|slot 3|third available|third slot)\b", user_lower):
                slot_idx = 2
            elif re.search(r"\b(book|confirm|yes|proceed|schedule|ok|please)\b", user_lower):
                # When user says "book", "confirm", "yes", default to option 1
                slot_idx = 0
            else:
                # Check day of week match
                for idx, slot in enumerate(available_slots):
                    fmt = slot.get("formatted", "").lower()
                    for day in ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]:
                        if day in user_lower and day in fmt:
                            slot_idx = idx
                            break
                    if slot_idx is not None:
                        break

            if slot_idx is not None and slot_idx < len(available_slots):
                selected_slot = available_slots[slot_idx]

        # Fallback slot booking if doctor selected but slots were not in context
        if not selected_slot and context.get("selected_doctor_id") and re.search(r"\b(book|option|slot|first|1|schedule|confirm|yes)\b", user_lower):
            doc_id = context.get("selected_doctor_id")
            return {
                "text": "Retrieving your requested slot and verifying EHR availability...",
                "tool_calls": [
                    {
                        "name": "check_availability",
                        "args": {"doctor_id": doc_id}
                    }
                ],
                "timeline_event": "AVAILABILITY",
            }

        if selected_slot:
            doc_id = selected_slot.get("doctor_id") or context.get("selected_doctor_id")
            start_iso = selected_slot.get("start_time")
            doc_name = selected_slot.get("doctor_name", "Doctor")
            return {
                "text": f"Booking your appointment with {doc_name} for {selected_slot.get('formatted')}. Verifying external EHR schedule now...",
                "tool_calls": [
                    {
                        "name": "create_appointment",
                        "args": {
                            "doctor_id": doc_id,
                            "start_time": start_iso,
                            "consultation_type": "IN_PERSON",
                            "reason_for_visit": context.get("chief_complaint") or "Orthopedic / Medical Consultation",
                        }
                    }
                ],
                "selected_slot": selected_slot,
                "timeline_event": "BOOKING_REQUESTED",
            }

        # 4. Intent: Doctor / Availability Discovery
        # Check for specialty or doctor query
        specialty_match = None
        if "orthopedic" in user_lower or "shoulder" in user_lower or "knee" in user_lower or "bone" in user_lower:
            specialty_match = "Orthopedics"
        elif "cardio" in user_lower or "heart" in user_lower:
            specialty_match = "Cardiology"
        elif "derma" in user_lower or "skin" in user_lower:
            specialty_match = "Dermatology"
        elif "general" in user_lower or "fever" in user_lower or "checkup" in user_lower:
            specialty_match = "General Medicine"

        if specialty_match or "doctor" in user_lower or "appointment" in user_lower or "schedule" in user_lower:
            spec = specialty_match or "Orthopedics"
            return {
                "text": f"I can help you schedule an appointment with an {spec} specialist. Let me check the doctor directory and real live availability...",
                "tool_calls": [
                    {
                        "name": "search_doctors",
                        "args": {"specialty_name": spec}
                    }
                ],
                "next_action": "check_availability",
                "timeline_event": "DISCOVERY_STARTED",
            }

        # 5. Intent: Reschedule or Cancel
        if "reschedule" in user_lower:
            appt_id = context.get("current_appointment_id")
            return {
                "text": "I can help you reschedule your appointment. What day or time would you prefer?",
                "tool_calls": [],
            }

        if "cancel" in user_lower:
            appt_id = context.get("current_appointment_id")
            if appt_id:
                return {
                    "text": "Cancelling your appointment and releasing the slot...",
                    "tool_calls": [
                        {
                            "name": "cancel_appointment",
                            "args": {"appointment_id": appt_id, "reason": "Patient requested cancellation via assistant."}
                        }
                    ],
                }

        # Default helpful administrative response
        return {
            "text": "Hello! I am your administrative healthcare access assistant. I can help you find specialists, check real appointment availability, book or reschedule visits, and complete your pre-visit health forms. How can I assist you today?",
            "tool_calls": [],
        }
