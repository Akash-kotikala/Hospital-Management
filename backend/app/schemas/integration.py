import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel
from app.db.models.enums import ReconciliationStatus, EHRSimulationMode


class FailureModeRequest(BaseModel):
    mode: EHRSimulationMode
    target_operation: Optional[str] = "CREATE_APPOINTMENT"
    active_until_resets: int = 1  # Trigger failure for next N operations


class FailureModeStatusResponse(BaseModel):
    current_mode: EHRSimulationMode
    active_until_resets: int
    message: str


class ReconciliationRecordResponse(BaseModel):
    id: str
    hospital_id: str
    correlation_id: str
    operation_id: str
    appointment_id: Optional[str] = None
    external_reference: Optional[str] = None
    failure_reason: str
    last_known_state: str
    verification_attempts: int
    resolution: Optional[str] = None
    status: ReconciliationStatus
    escalated_to_human: bool
    created_at: datetime.datetime
    updated_at: datetime.datetime

    model_config = {"from_attributes": True}


class ReconciliationResolveRequest(BaseModel):
    resolution: str
    mark_as: ReconciliationStatus = ReconciliationStatus.RESOLVED


class IntegrationOperationResponse(BaseModel):
    id: str
    hospital_id: str
    operation_type: str
    correlation_id: str
    operation_id: str
    endpoint: str
    status: str
    duration_ms: int
    error_details: Optional[str] = None
    created_at: datetime.datetime

    model_config = {"from_attributes": True}
