import uuid
import datetime
from typing import Optional, List, Dict, Any
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.integration import ReconciliationRecord, IntegrationOperation, IntegrationVerification
from app.db.models.appointment import Appointment, AppointmentHistory
from app.db.models.enums import ReconciliationStatus, AppointmentStatus
from app.integrations.mock_ehr import mock_ehr_connector
from app.services.audit_service import AuditService
from app.core.logging import logger


class ReconciliationService:
    @staticmethod
    async def create_reconciliation_record(
        db: AsyncSession,
        hospital_id: str,
        correlation_id: str,
        operation_id: str,
        appointment_id: Optional[str],
        failure_reason: str,
        last_known_state: str,
        external_reference: Optional[str] = None,
        escalated_to_human: bool = False,
    ) -> ReconciliationRecord:
        record = ReconciliationRecord(
            hospital_id=hospital_id,
            correlation_id=correlation_id,
            operation_id=operation_id,
            appointment_id=appointment_id,
            external_reference=external_reference,
            failure_reason=failure_reason,
            last_known_state=last_known_state,
            verification_attempts=1,
            status=ReconciliationStatus.ESCALATED if escalated_to_human else ReconciliationStatus.OPEN,
            escalated_to_human=escalated_to_human,
        )
        db.add(record)
        await db.flush()

        await AuditService.log_audit_event(
            db=db,
            action="RECONCILIATION_RECORD_CREATED",
            resource_type="RECONCILIATION",
            resource_id=record.id,
            hospital_id=hospital_id,
            correlation_id=correlation_id,
            operation_id=operation_id,
            details={
                "appointment_id": appointment_id,
                "failure_reason": failure_reason,
                "status": record.status.value,
            }
        )
        return record

    @staticmethod
    async def handle_booking_timeout_recovery(
        db: AsyncSession,
        appointment: Appointment,
        correlation_id: str,
        operation_id: str,
    ) -> Dict[str, Any]:
        """
        Executes the mandatory failure/recovery path:
        Timeout -> UNKNOWN_OUTCOME -> Query external system ->
        If found: Synchronize and confirm without duplicate booking.
        If not found: Safely mark failed or retry.
        If unknown: Flag RECONCILIATION_REQUIRED + escalate to human.
        """
        logger.info(f"Initiating timeout recovery for appointment {appointment.id} (idempotency={appointment.idempotency_key})")
        appointment.status = AppointmentStatus.SYNCHRONIZATION_PENDING
        await db.flush()

        # 1. Check external system using idempotency key to determine actual state
        ehr_match = await mock_ehr_connector.find_appointment_by_idempotency_key(appointment.idempotency_key)

        if ehr_match:
            # Case A: External system DID create the appointment despite client timeout
            external_id = ehr_match["external_id"]
            logger.info(f"Recovery found external appointment {external_id}. Synchronizing state.")

            appointment.external_appointment_id = external_id
            appointment.status = AppointmentStatus.CONFIRMED

            # Log verification
            verification = IntegrationVerification(
                hospital_id=appointment.hospital_id,
                appointment_id=appointment.id,
                external_appointment_id=external_id,
                verification_status="MATCH",
                details={"recovery_path": "TIMEOUT_RESOLVED", "ehr_record": ehr_match},
            )
            db.add(verification)

            # Record history
            history = AppointmentHistory(
                appointment_id=appointment.id,
                hospital_id=appointment.hospital_id,
                from_status=AppointmentStatus.SYNCHRONIZATION_PENDING.value,
                to_status=AppointmentStatus.CONFIRMED.value,
                trigger_reason="Timeout recovery verified external booking existence. State synchronized.",
                correlation_id=correlation_id,
                details={"external_appointment_id": external_id},
            )
            db.add(history)
            await db.flush()

            # Record resolved reconciliation audit
            rec = await ReconciliationService.create_reconciliation_record(
                db=db,
                hospital_id=appointment.hospital_id,
                correlation_id=correlation_id,
                operation_id=operation_id,
                appointment_id=appointment.id,
                failure_reason="EHR Timeout during create; resolved by idempotency verification query.",
                last_known_state="UNKNOWN_OUTCOME",
                external_reference=external_id,
            )
            rec.status = ReconciliationStatus.RESOLVED
            rec.resolution = f"External appointment found ({external_id}) and synchronized to CONFIRMED. Duplicate prevented."
            await db.flush()

            return {
                "recovered": True,
                "status": AppointmentStatus.CONFIRMED.value,
                "external_id": external_id,
                "message": "EHR Timeout encountered, but external verification confirmed appointment. State synchronized successfully.",
                "reconciliation_id": rec.id,
            }

        else:
            # Case B: External appointment truly does not exist. Safe to abort or flag.
            logger.warning(f"Recovery query found no external record for idempotency key {appointment.idempotency_key}.")
            appointment.status = AppointmentStatus.RECONCILIATION_REQUIRED

            rec = await ReconciliationService.create_reconciliation_record(
                db=db,
                hospital_id=appointment.hospital_id,
                correlation_id=correlation_id,
                operation_id=operation_id,
                appointment_id=appointment.id,
                failure_reason="EHR Timeout: External record not found on verification.",
                last_known_state="UNKNOWN_OUTCOME",
                escalated_to_human=True,
            )
            rec.resolution = "Escalated to human staff to verify provider calendar."
            await db.flush()

            return {
                "recovered": False,
                "status": AppointmentStatus.RECONCILIATION_REQUIRED.value,
                "message": "EHR Timeout occurred and external record could not be confirmed. Escalated to human administrator.",
                "reconciliation_id": rec.id,
            }

    @staticmethod
    async def list_records(
        db: AsyncSession,
        hospital_id: Optional[str] = None,
        status: Optional[ReconciliationStatus] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> List[ReconciliationRecord]:
        query = select(ReconciliationRecord).offset(skip).limit(limit).order_by(ReconciliationRecord.created_at.desc())
        if hospital_id:
            query = query.where(ReconciliationRecord.hospital_id == hospital_id)
        if status:
            query = query.where(ReconciliationRecord.status == status)
        result = await db.execute(query)
        return list(result.scalars().all())

    @staticmethod
    async def resolve_record(
        db: AsyncSession,
        record_id: str,
        resolution: str,
        mark_as: ReconciliationStatus = ReconciliationStatus.RESOLVED,
    ) -> ReconciliationRecord:
        record = await db.get(ReconciliationRecord, record_id)
        if not record:
            raise EntityNotFoundException("ReconciliationRecord", record_id)

        record.status = mark_as
        record.resolution = resolution
        record.updated_at = datetime.datetime.now(datetime.timezone.utc)
        await db.flush()
        return record
