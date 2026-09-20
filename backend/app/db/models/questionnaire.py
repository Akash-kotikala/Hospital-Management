import uuid
import datetime
from typing import Optional, List
from sqlalchemy import String, Text, Integer, Boolean, Enum, JSON, ForeignKey, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base, TimestampMixin, TenantMixin
from app.db.models.enums import QuestionType


class Questionnaire(Base, TimestampMixin, TenantMixin):
    __tablename__ = "questionnaires"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    specialty_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("specialties.id", ondelete="SET NULL"), nullable=True, index=True)
    doctor_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("doctors.id", ondelete="SET NULL"), nullable=True, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    questions: Mapped[List["QuestionnaireQuestion"]] = relationship("QuestionnaireQuestion", back_populates="questionnaire", cascade="all, delete-orphan", order_by="QuestionnaireQuestion.order_index")
    responses: Mapped[List["QuestionnaireResponse"]] = relationship("QuestionnaireResponse", back_populates="questionnaire", cascade="all, delete-orphan")


class QuestionnaireQuestion(Base, TimestampMixin):
    __tablename__ = "questionnaire_questions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    questionnaire_id: Mapped[str] = mapped_column(String(36), ForeignKey("questionnaires.id", ondelete="CASCADE"), nullable=False, index=True)
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    question_type: Mapped[QuestionType] = mapped_column(Enum(QuestionType), default=QuestionType.SHORT_TEXT, nullable=False)
    options: Mapped[list] = mapped_column(JSON, default=list, nullable=False)  # For choice / multiple choice
    is_required: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    order_index: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    validation_rules: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    questionnaire: Mapped["Questionnaire"] = relationship("Questionnaire", back_populates="questions")


class QuestionnaireResponse(Base, TimestampMixin, TenantMixin):
    __tablename__ = "questionnaire_responses"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    questionnaire_id: Mapped[str] = mapped_column(String(36), ForeignKey("questionnaires.id", ondelete="CASCADE"), nullable=False, index=True)
    appointment_id: Mapped[str] = mapped_column(String(36), ForeignKey("appointments.id", ondelete="CASCADE"), nullable=False, index=True)
    patient_id: Mapped[str] = mapped_column(String(36), ForeignKey("patients.id", ondelete="CASCADE"), nullable=False, index=True)

    answers: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)  # {question_id: answer_value}
    is_completed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    completed_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Doctor review
    reviewed_by_doctor_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("doctors.id", ondelete="SET NULL"), nullable=True)
    reviewed_at: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    doctor_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    questionnaire: Mapped["Questionnaire"] = relationship("Questionnaire", back_populates="responses")
    appointment: Mapped["Appointment"] = relationship("Appointment", back_populates="questionnaire_responses")
    patient: Mapped["Patient"] = relationship("Patient", back_populates="questionnaire_responses")
