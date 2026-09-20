import uuid
import datetime
from typing import Optional, List
from sqlalchemy import String, Integer, Text, Enum, JSON, ForeignKey, DateTime, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base, TimestampMixin, TenantMixin
from app.db.models.enums import DoctorStatus


class Doctor(Base, TimestampMixin, TenantMixin):
    __tablename__ = "doctors"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, unique=True)
    specialty_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("specialties.id", ondelete="SET NULL"), nullable=True, index=True)
    department_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("departments.id", ondelete="SET NULL"), nullable=True)

    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    photo_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    qualifications: Mapped[str] = mapped_column(String(255), default="MD", nullable=False)
    experience_years: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    languages: Mapped[list] = mapped_column(JSON, default=lambda: ["English"], nullable=False)
    consultation_types: Mapped[list] = mapped_column(JSON, default=lambda: ["IN_PERSON", "VIDEO"], nullable=False)
    appointment_duration_minutes: Mapped[int] = mapped_column(Integer, default=30, nullable=False)
    external_provider_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    status: Mapped[DoctorStatus] = mapped_column(Enum(DoctorStatus), default=DoctorStatus.ACTIVE, nullable=False, index=True)
    bio: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    hospital: Mapped["Hospital"] = relationship("Hospital", back_populates="doctors")
    user: Mapped[Optional["User"]] = relationship("User", back_populates="doctor_profile")
    specialty: Mapped[Optional["Specialty"]] = relationship("Specialty")
    department: Mapped[Optional["Department"]] = relationship("Department")
    calendar: Mapped[Optional["Calendar"]] = relationship("Calendar", back_populates="doctor", uselist=False, cascade="all, delete-orphan")
    blocked_slots: Mapped[List["BlockedSlot"]] = relationship("BlockedSlot", back_populates="doctor", cascade="all, delete-orphan")
    appointments: Mapped[List["Appointment"]] = relationship("Appointment", back_populates="doctor")


class Calendar(Base, TimestampMixin, TenantMixin):
    __tablename__ = "calendars"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    doctor_id: Mapped[str] = mapped_column(String(36), ForeignKey("doctors.id", ondelete="CASCADE"), unique=True, nullable=False)
    timezone: Mapped[str] = mapped_column(String(50), default="UTC", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    doctor: Mapped["Doctor"] = relationship("Doctor", back_populates="calendar")
    availabilities: Mapped[List["Availability"]] = relationship("Availability", back_populates="calendar", cascade="all, delete-orphan")


class Availability(Base, TimestampMixin, TenantMixin):
    __tablename__ = "availabilities"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    calendar_id: Mapped[str] = mapped_column(String(36), ForeignKey("calendars.id", ondelete="CASCADE"), nullable=False, index=True)
    day_of_week: Mapped[int] = mapped_column(Integer, nullable=False)  # 0 = Monday, 6 = Sunday
    start_time: Mapped[str] = mapped_column(String(8), nullable=False)  # "09:00"
    end_time: Mapped[str] = mapped_column(String(8), nullable=False)    # "17:00"
    slot_duration_minutes: Mapped[int] = mapped_column(Integer, default=30, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    calendar: Mapped["Calendar"] = relationship("Calendar", back_populates="availabilities")


class BlockedSlot(Base, TimestampMixin, TenantMixin):
    __tablename__ = "blocked_slots"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    doctor_id: Mapped[str] = mapped_column(String(36), ForeignKey("doctors.id", ondelete="CASCADE"), nullable=False, index=True)
    start_time: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    end_time: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    reason: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    is_all_day: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    doctor: Mapped["Doctor"] = relationship("Doctor", back_populates="blocked_slots")
