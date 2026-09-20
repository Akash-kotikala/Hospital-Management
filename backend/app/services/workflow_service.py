import uuid
import datetime
from typing import Dict, Any, Optional, List
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.workflow import Workflow, WorkflowExecution
from app.db.models.enums import WorkflowStatus, NotificationChannel
from app.services.notification_service import NotificationService
from app.services.audit_service import AuditService
from app.core.logging import logger


class WorkflowService:
    @staticmethod
    async def dispatch_event(
        db: AsyncSession,
        event_name: str,
        hospital_id: str,
        payload: Dict[str, Any],
        correlation_id: Optional[str] = None,
    ):
        """
        Asynchronous workflow dispatcher:
        Matches event triggers and executes associated workflow actions.
        """
        logger.info(f"Workflow event dispatched: '{event_name}' for hospital '{hospital_id}'")

        # 1. Log operational event
        await AuditService.log_operational_event(
            db=db,
            event_type=f"WORKFLOW_TRIGGER_{event_name.upper()}",
            service_name="WorkflowEngine",
            details=payload,
            correlation_id=correlation_id,
        )

        # 2. Query configured workflows for this event
        wf_query = await db.execute(
            select(Workflow).where(
                Workflow.hospital_id == hospital_id,
                Workflow.event_trigger == event_name,
                Workflow.is_active == True,
            )
        )
        workflows = list(wf_query.scalars().all())

        # If no custom workflow, execute default system event handlers
        if not workflows:
            await WorkflowService._execute_default_event_handler(db, event_name, hospital_id, payload, correlation_id)
            return

        for wf in workflows:
            execution = WorkflowExecution(
                workflow_id=wf.id,
                hospital_id=hospital_id,
                trigger_event=event_name,
                context_data=payload,
                status=WorkflowStatus.RUNNING,
                current_step=0,
                result={},
            )
            db.add(execution)
            await db.flush()

            try:
                for idx, action in enumerate(wf.actions):
                    await WorkflowService._execute_action(db, action, hospital_id, payload)
                    execution.current_step = idx + 1

                execution.status = WorkflowStatus.COMPLETED
                execution.result = {"status": "success", "steps_executed": len(wf.actions)}
            except Exception as exc:
                logger.error(f"Workflow execution {execution.id} failed: {exc}")
                execution.status = WorkflowStatus.FAILED
                execution.error_message = str(exc)

            await db.flush()

    @staticmethod
    async def _execute_default_event_handler(
        db: AsyncSession,
        event_name: str,
        hospital_id: str,
        payload: Dict[str, Any],
        correlation_id: Optional[str],
    ):
        """Default platform actions for core healthcare lifecycle events."""
        if event_name == "appointment_booked":
            patient_email = payload.get("patient_email") or "patient@example.com"
            doctor_name = payload.get("doctor_name", "your doctor")
            start_time = payload.get("start_time", "scheduled time")
            appt_id = payload.get("appointment_id")
            patient_id = payload.get("patient_id")

            # 1. Dispatch in-app booking confirmation
            await NotificationService.send_notification(
                db=db,
                hospital_id=hospital_id,
                recipient=patient_email,
                subject=f"Appointment Confirmed with {doctor_name}",
                content=f"Your appointment has been verified and confirmed for {start_time}. Please complete your pre-visit questionnaire.",
                channel=NotificationChannel.IN_APP,
                patient_id=patient_id,
                metadata={"appointment_id": appt_id, "event": "appointment_booked"}
            )

            # 2. Schedule pre-visit questionnaire reminder
            await NotificationService.send_notification(
                db=db,
                hospital_id=hospital_id,
                recipient=patient_email,
                subject="Pre-Visit Health Questionnaire Ready",
                content=f"Please answer your pre-visit questionnaire before your upcoming visit with {doctor_name}.",
                channel=NotificationChannel.IN_APP,
                patient_id=patient_id,
                metadata={"appointment_id": appt_id, "event": "questionnaire_assigned"}
            )

        elif event_name == "appointment_rescheduled":
            patient_email = payload.get("patient_email") or "patient@example.com"
            new_time = payload.get("new_time", "newly scheduled time")
            await NotificationService.send_notification(
                db=db,
                hospital_id=hospital_id,
                recipient=patient_email,
                subject="Appointment Rescheduled",
                content=f"Your appointment has been rescheduled to {new_time}.",
                channel=NotificationChannel.IN_APP,
                patient_id=payload.get("patient_id"),
                metadata={"appointment_id": payload.get("appointment_id")}
            )

        elif event_name == "appointment_cancelled":
            patient_email = payload.get("patient_email") or "patient@example.com"
            await NotificationService.send_notification(
                db=db,
                hospital_id=hospital_id,
                recipient=patient_email,
                subject="Appointment Cancelled",
                content="Your appointment has been successfully cancelled and released.",
                channel=NotificationChannel.IN_APP,
                patient_id=payload.get("patient_id"),
                metadata={"appointment_id": payload.get("appointment_id")}
            )

        elif event_name == "reconciliation_required":
            # Alert hospital administrators
            await NotificationService.send_notification(
                db=db,
                hospital_id=hospital_id,
                recipient="hospital-admin@healthcare.local",
                subject="CRITICAL: Integration Reconciliation Required",
                content=f"Appointment {payload.get('appointment_id')} encountered EHR integration failure. Immediate review required.",
                channel=NotificationChannel.IN_APP,
                metadata=payload
            )

    @staticmethod
    async def _execute_action(db: AsyncSession, action: Dict[str, Any], hospital_id: str, payload: Dict[str, Any]):
        action_type = action.get("type")
        if action_type == "send_notification":
            await NotificationService.send_notification(
                db=db,
                hospital_id=hospital_id,
                recipient=action.get("recipient") or payload.get("patient_email", "patient@example.com"),
                subject=action.get("subject", "Healthcare Notification"),
                content=action.get("content", "You have a new update."),
                channel=NotificationChannel(action.get("channel", "IN_APP")),
            )
