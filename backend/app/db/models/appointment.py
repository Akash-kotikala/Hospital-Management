import uuid
import datetime
from typing import Optional, List
from sqlalchemy import String, Text, DateTime, Enum, JSON, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base, TimestampMixin, TenantMixin
from app.db.models.enums import AppointmentStatus, ConsultationType


class Appointment(Base, TimestampMixin, TenantMixin):
    __tablename__ = "appointments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    patient_id: Mapped[str] = mapped_column(String(36), ForeignKey("patients.id", ondelete="CASCADE"), nullable=False, index=True)
    doctor_id: Mapped[str] = mapped_column(String(36), ForeignKey("doctors.id", ondelete="CASCADE"), nullable=False, index=True)

    start_time: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    end_time: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    status: Mapped[AppointmentStatus] = mapped_column(
        Enum(AppointmentStatus), default=AppointmentStatus.REQUESTED, nullable=False, index=True
    )
    consultation_type: Mapped[ConsultationType] = mapped_column(
        Enum(ConsultationType), default=ConsultationType.IN_PERSON, nullable=False
    )
    reason_for_visit: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    chief_complaint: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # EHR and tracking references
    external_appointment_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    idempotency_key: Mapped[Optional[str]] = mapped_column(String(100), unique=True, nullable=True, index=True)
    correlation_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    operation_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    appointment_metadata: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    # Relationships
    patient: Mapped["Patient"] = relationship("Patient", back_populates="appointments")
    doctor: Mapped["Doctor"] = relationship("Doctor", back_populates="appointments")
    hospital: Mapped["Hospital"] = relationship("Hospital")
    history: Mapped[List["AppointmentHistory"]] = relationship("AppointmentHistory", back_populates="appointment", cascade="all, delete-orphan")
    questionnaire_responses: Mapped[List["QuestionnaireResponse"]] = relationship("QuestionnaireResponse", back_populates="appointment")


class AppointmentHistory(Base, TimestampMixin, TenantMixin):
    __tablename__ = "appointment_history"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    appointment_id: Mapped[str] = mapped_column(String(36), ForeignKey("appointments.id", ondelete="CASCADE"), nullable=False, index=True)
    from_status: Mapped[str] = mapped_column(String(50), nullable=False)
    to_status: Mapped[str] = mapped_column(String(50), nullable=False)
    trigger_reason: Mapped[str] = mapped_column(String(255), nullable=False)
    changed_by_user_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    correlation_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    details: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    appointment: Mapped["Appointment"] = relationship("Appointment", back_populates="history")
