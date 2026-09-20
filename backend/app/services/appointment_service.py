import uuid
import datetime
from typing import Optional, List, Dict, Any
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import (
    EntityNotFoundException,
    SlotUnavailableException,
    InvalidStateTransitionException,
    EHRTimeoutException,
    EHRIntegrationException,
)
from app.db.models.appointment import Appointment, AppointmentHistory
from app.db.models.doctor import Doctor
from app.db.models.patient import Patient
from app.db.models.enums import AppointmentStatus, ConsultationType
from app.db.models.integration import IntegrationOperation, IntegrationVerification
from app.integrations.mock_ehr import mock_ehr_connector
from app.services.scheduling_service import SchedulingService
from app.services.reconciliation_service import ReconciliationService
from app.services.workflow_service import WorkflowService
from app.services.audit_service import AuditService
from app.schemas.appointment import AppointmentCreate, AppointmentReschedule, AppointmentCancel
from app.core.logging import logger, correlation_id_ctx, operation_id_ctx


VALID_TRANSITIONS: Dict[AppointmentStatus, List[AppointmentStatus]] = {
    AppointmentStatus.REQUESTED: [AppointmentStatus.PENDING, AppointmentStatus.CANCELLED, AppointmentStatus.FAILED],
    AppointmentStatus.PENDING: [
        AppointmentStatus.CONFIRMED,
        AppointmentStatus.FAILED,
        AppointmentStatus.SYNCHRONIZATION_PENDING,
        AppointmentStatus.RECONCILIATION_REQUIRED,
    ],
    AppointmentStatus.CONFIRMED: [
        AppointmentStatus.RESCHEDULED,
        AppointmentStatus.CANCELLED,
        AppointmentStatus.COMPLETED,
        AppointmentStatus.NO_SHOW,
    ],
    AppointmentStatus.RESCHEDULED: [
        AppointmentStatus.RESCHEDULED,
        AppointmentStatus.CANCELLED,
        AppointmentStatus.COMPLETED,
        AppointmentStatus.NO_SHOW,
    ],
    AppointmentStatus.SYNCHRONIZATION_PENDING: [
        AppointmentStatus.CONFIRMED,
        AppointmentStatus.RECONCILIATION_REQUIRED,
        AppointmentStatus.FAILED,
    ],
    AppointmentStatus.RECONCILIATION_REQUIRED: [
        AppointmentStatus.CONFIRMED,
        AppointmentStatus.FAILED,
        AppointmentStatus.CANCELLED,
    ],
    AppointmentStatus.CANCELLED: [],
    AppointmentStatus.COMPLETED: [],
    AppointmentStatus.NO_SHOW: [],
    AppointmentStatus.FAILED: [],
}


class AppointmentService:
    @staticmethod
    def validate_transition(current: AppointmentStatus, target: AppointmentStatus):
        allowed = VALID_TRANSITIONS.get(current, [])
        if target not in allowed:
            raise InvalidStateTransitionException(current.value, target.value)

    @staticmethod
    async def book_appointment(
        db: AsyncSession,
        appt_in: AppointmentCreate,
        patient_id: str,
        user_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        corr_id = correlation_id or correlation_id_ctx.get() or str(uuid.uuid4())
        op_id = operation_id_ctx.get() or str(uuid.uuid4())

        # 1. Fetch Doctor and calculate end_time if not provided
        doctor = await db.get(Doctor, appt_in.doctor_id)
        if not doctor:
            raise EntityNotFoundException("Doctor", appt_in.doctor_id)

        start_time = appt_in.start_time
        if not appt_in.end_time:
            end_time = start_time + datetime.timedelta(minutes=doctor.appointment_duration_minutes)
        else:
            end_time = appt_in.end_time

        # 2. Final availability revalidation immediately before booking
        await SchedulingService.revalidate_slot_availability(db, doctor.id, start_time, end_time)

        # 3. Fetch Patient details
        patient = await db.get(Patient, patient_id)
        if not patient:
            raise EntityNotFoundException("Patient", patient_id)

        # 4. Check idempotency
        idempotency_key = appt_in.idempotency_key or f"IDEMP-{uuid.uuid4().hex[:12].upper()}"
        existing_idemp = await db.execute(select(Appointment).where(Appointment.idempotency_key == idempotency_key))
        if existing_idemp.scalar_one_or_none():
            existing = existing_idemp.scalar_one()
            return {"appointment": existing, "status": existing.status.value, "is_duplicate": True}

        # 5. Create internal appointment in PENDING state
        appointment = Appointment(
            hospital_id=doctor.hospital_id,
            patient_id=patient.id,
            doctor_id=doctor.id,
            start_time=start_time,
            end_time=end_time,
            status=AppointmentStatus.PENDING,
            consultation_type=appt_in.consultation_type,
            reason_for_visit=appt_in.reason_for_visit,
            chief_complaint=appt_in.chief_complaint,
            idempotency_key=idempotency_key,
            correlation_id=corr_id,
            operation_id=op_id,
        )
        db.add(appointment)
        await db.flush()

        history_pending = AppointmentHistory(
            appointment_id=appointment.id,
            hospital_id=appointment.hospital_id,
            from_status="NONE",
            to_status=AppointmentStatus.PENDING.value,
            trigger_reason="Initial booking requested. Slot reserved pending EHR verification.",
            changed_by_user_id=user_id,
            correlation_id=corr_id,
            details={"start_time": start_time.isoformat(), "end_time": end_time.isoformat()},
        )
        db.add(history_pending)
        await db.flush()

        # 6. Call EHR Connector
        ehr_payload = {
            "doctor_id": doctor.id,
            "patient_id": patient.id,
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "idempotency_key": idempotency_key,
            "correlation_id": corr_id,
        }

        op_record = IntegrationOperation(
            hospital_id=appointment.hospital_id,
            operation_type="CREATE_APPOINTMENT",
            correlation_id=corr_id,
            operation_id=op_id,
            endpoint=f"{mock_ehr_connector.__class__.__name__}/appointments",
            request_payload=ehr_payload,
            response_payload={},
            status="PENDING",
        )
        db.add(op_record)
        await db.flush()

        try:
            ehr_res = await mock_ehr_connector.create_appointment(ehr_payload)
            op_record.status = "SUCCESS"
            op_record.response_payload = ehr_res
            await db.flush()

            # 7. Two-phase verification: Query external system to verify record
            external_id = ehr_res["external_id"]
            verification_res = await mock_ehr_connector.verify_appointment(external_id)

            if not verification_res.get("verified"):
                raise EHRIntegrationException(f"External verification failed for EHR record {external_id}")

            verification = IntegrationVerification(
                hospital_id=appointment.hospital_id,
                appointment_id=appointment.id,
                external_appointment_id=external_id,
                verification_status="MATCH",
                details=verification_res,
            )
            db.add(verification)

            # 8. Synchronize internal state -> CONFIRMED
            AppointmentService.validate_transition(appointment.status, AppointmentStatus.CONFIRMED)
            appointment.status = AppointmentStatus.CONFIRMED
            appointment.external_appointment_id = external_id

            history_confirmed = AppointmentHistory(
                appointment_id=appointment.id,
                hospital_id=appointment.hospital_id,
                from_status=AppointmentStatus.PENDING.value,
                to_status=AppointmentStatus.CONFIRMED.value,
                trigger_reason="EHR verification succeeded. Appointment confirmed.",
                changed_by_user_id=user_id,
                correlation_id=corr_id,
                details={"external_appointment_id": external_id},
            )
            db.add(history_confirmed)
            await db.flush()

            # 9. Trigger workflow & notifications
            await WorkflowService.dispatch_event(
                db=db,
                event_name="appointment_booked",
                hospital_id=appointment.hospital_id,
                payload={
                    "appointment_id": appointment.id,
                    "patient_id": patient.id,
                    "patient_email": patient.email,
                    "doctor_name": doctor.name,
                    "start_time": start_time.strftime("%A, %b %d at %I:%M %p"),
                },
                correlation_id=corr_id,
            )

            await AuditService.log_audit_event(
                db=db,
                action="APPOINTMENT_CONFIRMED",
                resource_type="APPOINTMENT",
                resource_id=appointment.id,
                hospital_id=appointment.hospital_id,
                user_id=user_id,
                correlation_id=corr_id,
                operation_id=op_id,
                details={"external_appointment_id": external_id, "start_time": start_time.isoformat()}
            )

            return {
                "appointment": appointment,
                "status": "CONFIRMED",
                "external_id": external_id,
                "message": "Appointment booked and verified with external EHR.",
            }

        except EHRTimeoutException as timeout_exc:
            op_record.status = "TIMEOUT"
            op_record.error_details = str(timeout_exc)
            await db.flush()

            logger.warning(f"EHR Timeout during booking. Triggering timeout recovery state machine.")
            # Execute the mandatory recovery path:
            recovery_result = await ReconciliationService.handle_booking_timeout_recovery(
                db=db,
                appointment=appointment,
                correlation_id=corr_id,
                operation_id=op_id,
            )
            return {
                "appointment": appointment,
                "status": appointment.status.value,
                "timeout_encountered": True,
                "recovery": recovery_result,
            }

        except Exception as exc:
            op_record.status = "ERROR"
            op_record.error_details = str(exc)
            appointment.status = AppointmentStatus.FAILED
            await db.flush()
            raise

    @staticmethod
    async def reschedule_appointment(
        db: AsyncSession,
        appointment_id: str,
        reschedule_in: AppointmentReschedule,
        user_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
    ) -> Appointment:
        corr_id = correlation_id or correlation_id_ctx.get() or str(uuid.uuid4())
        appointment = await db.get(Appointment, appointment_id)
        if not appointment:
            raise EntityNotFoundException("Appointment", appointment_id)

        AppointmentService.validate_transition(appointment.status, AppointmentStatus.RESCHEDULED)

        doctor = await db.get(Doctor, appointment.doctor_id)
        new_start = reschedule_in.new_start_time
        new_end = reschedule_in.new_end_time or (new_start + datetime.timedelta(minutes=doctor.appointment_duration_minutes))

        # Revalidate new slot (excluding current appointment)
        await SchedulingService.revalidate_slot_availability(db, doctor.id, new_start, new_end, exclude_appointment_id=appointment.id)

        # Update external EHR if connected
        if appointment.external_appointment_id:
            await mock_ehr_connector.update_appointment(
                appointment.external_appointment_id,
                {"start_time": new_start.isoformat(), "end_time": new_end.isoformat()}
            )

        old_start = appointment.start_time
        appointment.start_time = new_start
        appointment.end_time = new_end
        appointment.status = AppointmentStatus.RESCHEDULED

        history = AppointmentHistory(
            appointment_id=appointment.id,
            hospital_id=appointment.hospital_id,
            from_status=AppointmentStatus.CONFIRMED.value,
            to_status=AppointmentStatus.RESCHEDULED.value,
            trigger_reason=reschedule_in.reason or "Patient reschedule",
            changed_by_user_id=user_id,
            correlation_id=corr_id,
            details={"old_start": old_start.isoformat(), "new_start": new_start.isoformat()},
        )
        db.add(history)
        await db.flush()

        # Trigger workflow
        patient = await db.get(Patient, appointment.patient_id)
        await WorkflowService.dispatch_event(
            db=db,
            event_name="appointment_rescheduled",
            hospital_id=appointment.hospital_id,
            payload={
                "appointment_id": appointment.id,
                "patient_id": appointment.patient_id,
                "patient_email": patient.email if patient else "",
                "new_time": new_start.strftime("%A, %b %d at %I:%M %p"),
            },
            correlation_id=corr_id,
        )
        return appointment

    @staticmethod
    async def cancel_appointment(
        db: AsyncSession,
        appointment_id: str,
        cancel_in: AppointmentCancel,
        user_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
    ) -> Appointment:
        corr_id = correlation_id or correlation_id_ctx.get() or str(uuid.uuid4())
        appointment = await db.get(Appointment, appointment_id)
        if not appointment:
            raise EntityNotFoundException("Appointment", appointment_id)

        AppointmentService.validate_transition(appointment.status, AppointmentStatus.CANCELLED)

        # Cancel external EHR if connected
        if appointment.external_appointment_id:
            await mock_ehr_connector.cancel_appointment(
                appointment.external_appointment_id,
                reason=cancel_in.reason or "Patient cancellation"
            )

        prev_status = appointment.status.value
        appointment.status = AppointmentStatus.CANCELLED

        history = AppointmentHistory(
            appointment_id=appointment.id,
            hospital_id=appointment.hospital_id,
            from_status=prev_status,
            to_status=AppointmentStatus.CANCELLED.value,
            trigger_reason=cancel_in.reason or "Patient cancellation",
            changed_by_user_id=user_id,
            correlation_id=corr_id,
            details={"cancellation_reason": cancel_in.reason},
        )
        db.add(history)
        await db.flush()

        patient = await db.get(Patient, appointment.patient_id)
        await WorkflowService.dispatch_event(
            db=db,
            event_name="appointment_cancelled",
            hospital_id=appointment.hospital_id,
            payload={
                "appointment_id": appointment.id,
                "patient_id": appointment.patient_id,
                "patient_email": patient.email if patient else "",
            },
            correlation_id=corr_id,
        )
        return appointment

    @staticmethod
    async def get_appointment(db: AsyncSession, appointment_id: str) -> Appointment:
        result = await db.execute(
            select(Appointment)
            .options(
                selectinload(Appointment.history),
                selectinload(Appointment.doctor),
                selectinload(Appointment.patient),
            )
            .where(Appointment.id == appointment_id)
        )
        appt = result.scalar_one_or_none()
        if not appt:
            raise EntityNotFoundException("Appointment", appointment_id)
        return appt

    @staticmethod
    async def list_appointments(
        db: AsyncSession,
        hospital_id: Optional[str] = None,
        doctor_id: Optional[str] = None,
        patient_id: Optional[str] = None,
        status: Optional[AppointmentStatus] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> List[Appointment]:
        query = (
            select(Appointment)
            .options(
                selectinload(Appointment.history),
                selectinload(Appointment.doctor),
                selectinload(Appointment.patient),
            )
            .offset(skip)
            .limit(limit)
            .order_by(Appointment.start_time.desc())
        )
        if hospital_id:
            query = query.where(Appointment.hospital_id == hospital_id)
        if doctor_id:
            query = query.where(Appointment.doctor_id == doctor_id)
        if patient_id:
            query = query.where(Appointment.patient_id == patient_id)
        if status:
            query = query.where(Appointment.status == status)

        result = await db.execute(query)
        return list(result.scalars().all())
