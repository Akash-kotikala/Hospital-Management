import uuid
from typing import List, Optional
from sqlalchemy import String, Text, Enum, JSON, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base, TimestampMixin
from app.db.models.enums import HospitalStatus


class Hospital(Base, TimestampMixin):
    __tablename__ = "hospitals"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    address: Mapped[str] = mapped_column(String(500), nullable=False)
    phone: Mapped[str] = mapped_column(String(50), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    website: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    status: Mapped[HospitalStatus] = mapped_column(
        Enum(HospitalStatus), default=HospitalStatus.DRAFT, nullable=False, index=True
    )
    configuration: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    # Relationships
    departments: Mapped[List["Department"]] = relationship("Department", back_populates="hospital", cascade="all, delete-orphan")
    specialties: Mapped[List["Specialty"]] = relationship("Specialty", back_populates="hospital", cascade="all, delete-orphan")
    doctors: Mapped[List["Doctor"]] = relationship("Doctor", back_populates="hospital", cascade="all, delete-orphan")
    staff: Mapped[List["HospitalStaff"]] = relationship("HospitalStaff", back_populates="hospital", cascade="all, delete-orphan")


class Department(Base, TimestampMixin):
    __tablename__ = "departments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    hospital_id: Mapped[str] = mapped_column(String(36), ForeignKey("hospitals.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    hospital: Mapped["Hospital"] = relationship("Hospital", back_populates="departments")


class Specialty(Base, TimestampMixin):
    __tablename__ = "specialties"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    hospital_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("hospitals.id", ondelete="CASCADE"), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    hospital: Mapped[Optional["Hospital"]] = relationship("Hospital", back_populates="specialties")
