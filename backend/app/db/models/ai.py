import uuid
from typing import Optional, List
from sqlalchemy import String, Text, Boolean, Integer, Float, JSON, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base, TimestampMixin


class AIConversation(Base, TimestampMixin):
    __tablename__ = "ai_conversations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    patient_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("patients.id", ondelete="SET NULL"), nullable=True, index=True)
    hospital_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("hospitals.id", ondelete="SET NULL"), nullable=True, index=True)
    session_type: Mapped[str] = mapped_column(String(20), default="CHAT", nullable=False)  # "CHAT" or "VOICE"
    title: Mapped[str] = mapped_column(String(255), default="Healthcare Scheduling Session", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relationships
    messages: Mapped[List["AIMessage"]] = relationship("AIMessage", back_populates="conversation", cascade="all, delete-orphan", order_by="AIMessage.created_at", lazy="selectin")
    context: Mapped[Optional["AIContext"]] = relationship("AIContext", back_populates="conversation", uselist=False, cascade="all, delete-orphan", lazy="selectin")
    capabilities: Mapped[List["CapabilityExecution"]] = relationship("CapabilityExecution", back_populates="conversation", cascade="all, delete-orphan", lazy="selectin")


class AIMessage(Base, TimestampMixin):
    __tablename__ = "ai_messages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    conversation_id: Mapped[str] = mapped_column(String(36), ForeignKey("ai_conversations.id", ondelete="CASCADE"), nullable=False, index=True)
    sender: Mapped[str] = mapped_column(String(20), nullable=False)  # "USER", "ASSISTANT", "SYSTEM"
    content: Mapped[str] = mapped_column(Text, nullable=False)
    tool_calls: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    tool_results: Mapped[list] = mapped_column(JSON, default=list, nullable=False)

    conversation: Mapped["AIConversation"] = relationship("AIConversation", back_populates="messages")


class AIContext(Base, TimestampMixin):
    __tablename__ = "ai_contexts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    conversation_id: Mapped[str] = mapped_column(String(36), ForeignKey("ai_conversations.id", ondelete="CASCADE"), unique=True, nullable=False)
    current_intent: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    selected_hospital_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    selected_doctor_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    selected_slot: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    current_appointment_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True)
    relevant_preferences: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    workflow_state: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    conversation: Mapped["AIConversation"] = relationship("AIConversation", back_populates="context")


class CapabilityExecution(Base, TimestampMixin):
    __tablename__ = "capability_executions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    conversation_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("ai_conversations.id", ondelete="SET NULL"), nullable=True, index=True)
    capability_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    input_payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    output_payload: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="SUCCESS", nullable=False)  # SUCCESS, FAILED
    execution_duration_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    correlation_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    operation_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)

    conversation: Mapped[Optional["AIConversation"]] = relationship("AIConversation", back_populates="capabilities")


class AIEvaluation(Base, TimestampMixin):
    __tablename__ = "ai_evaluations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    conversation_id: Mapped[str] = mapped_column(String(36), ForeignKey("ai_conversations.id", ondelete="CASCADE"), nullable=False, index=True)
    safety_passed: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    medical_escalation_triggered: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    hallucination_check_passed: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    feedback_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
