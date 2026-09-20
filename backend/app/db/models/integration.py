import uuid
import datetime
from typing import Optional
from sqlalchemy import String, Text, Integer, Enum, JSON, ForeignKey, DateTime, Boolean
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base, TimestampMixin, TenantMixin
from app.db.models.enums import ReconciliationStatus


class HealthcareSystemConnection(Base, TimestampMixin, TenantMixin):
    __tablename__ = "healthcare_system_connections"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    system_name: Mapped[str] = mapped_column(String(100), default="MockEHR", nullable=False)
    base_url: Mapped[str] = mapped_column(String(255), nullable=False)
    auth_config: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class ExternalIdentifierMapping(Base, TimestampMixin, TenantMixin):
    __tablename__ = "external_identifier_mappings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    internal_entity_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)  # PATIENT, DOCTOR, APPOINTMENT
    internal_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    external_system_name: Mapped[str] = mapped_column(String(50), default="MockEHR", nullable=False)
    external_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)


class IntegrationOperation(Base, TimestampMixin, TenantMixin):
    __tablename__ = "integration_operations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    operation_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)  # CREATE_APPOINTMENT, VERIFY, CANCEL
    correlation_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    operation_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    endpoint: Mapped[str] = mapped_column(String(255), nullable=False)
    request_payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    response_payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)  # SUCCESS, TIMEOUT, ERROR
    error_details: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class IntegrationVerification(Base, TimestampMixin, TenantMixin):
    __tablename__ = "integration_verifications"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    appointment_id: Mapped[str] = mapped_column(String(36), ForeignKey("appointments.id", ondelete="CASCADE"), nullable=False, index=True)
    external_appointment_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    verification_status: Mapped[str] = mapped_column(String(50), nullable=False)  # MATCH, MISMATCH, NOT_FOUND, TIMEOUT
    details: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    verified_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.datetime.now(datetime.timezone.utc), nullable=False)


class ReconciliationRecord(Base, TimestampMixin, TenantMixin):
    __tablename__ = "reconciliation_records"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    correlation_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    operation_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    appointment_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    external_reference: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    failure_reason: Mapped[str] = mapped_column(String(255), nullable=False)
    last_known_state: Mapped[str] = mapped_column(String(50), nullable=False)
    verification_attempts: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    resolution: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[ReconciliationStatus] = mapped_column(
        Enum(ReconciliationStatus), default=ReconciliationStatus.OPEN, nullable=False, index=True
    )
    escalated_to_human: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
