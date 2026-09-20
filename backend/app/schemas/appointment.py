import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel
from app.db.models.enums import AppointmentStatus, ConsultationType


class AppointmentCreate(BaseModel):
    doctor_id: str
    hospital_id: str
    patient_id: Optional[str] = None  # Inferred if patient is logged in
    start_time: datetime.datetime
    end_time: Optional[datetime.datetime] = None  # Can be computed via doctor.appointment_duration_minutes
    consultation_type: ConsultationType = ConsultationType.IN_PERSON
    reason_for_visit: Optional[str] = None
    chief_complaint: Optional[str] = None
    idempotency_key: Optional[str] = None


class AppointmentReschedule(BaseModel):
    new_start_time: datetime.datetime
    new_end_time: Optional[datetime.datetime] = None
    reason: Optional[str] = "Patient requested reschedule"


class AppointmentCancel(BaseModel):
    reason: Optional[str] = "Patient requested cancellation"


class AppointmentHistoryResponse(BaseModel):
    id: str
    from_status: str
    to_status: str
    trigger_reason: str
    created_at: datetime.datetime
    correlation_id: Optional[str] = None
    details: Dict[str, Any] = {}

    model_config = {"from_attributes": True}


class AppointmentResponse(BaseModel):
    id: str
    hospital_id: str
    patient_id: str
    doctor_id: str
    start_time: datetime.datetime
    end_time: datetime.datetime
    status: AppointmentStatus
    consultation_type: ConsultationType
    reason_for_visit: Optional[str] = None
    chief_complaint: Optional[str] = None
    notes: Optional[str] = None
    external_appointment_id: Optional[str] = None
    idempotency_key: Optional[str] = None
    correlation_id: Optional[str] = None
    operation_id: Optional[str] = None
    created_at: datetime.datetime
    history: List[AppointmentHistoryResponse] = []

    model_config = {"from_attributes": True}


class AppointmentTimelineStep(BaseModel):
    name: str
    status: str  # PENDING, IN_PROGRESS, SUCCESS, FAILED, RECOVERED
    timestamp: datetime.datetime
    details: Optional[str] = None
