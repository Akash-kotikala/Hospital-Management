import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel


class AuditEventResponse(BaseModel):
    id: str
    hospital_id: Optional[str] = None
    user_id: Optional[str] = None
    action: str
    resource_type: str
    resource_id: Optional[str] = None
    correlation_id: Optional[str] = None
    operation_id: Optional[str] = None
    ip_address: Optional[str] = None
    details: Dict[str, Any] = {}
    created_at: datetime.datetime

    model_config = {"from_attributes": True}


class OperationalEventResponse(BaseModel):
    id: str
    event_type: str
    severity: str
    service_name: str
    correlation_id: Optional[str] = None
    details: Dict[str, Any] = {}
    created_at: datetime.datetime

    model_config = {"from_attributes": True}


class AnalyticsOverviewResponse(BaseModel):
    total_hospitals: int
    active_doctors: int
    total_patients: int
    total_appointments: int
    confirmed_appointments: int
    reconciliation_records_open: int
    ai_conversations_total: int
    ehr_operations_total: int


class AnalyticsAppointmentsResponse(BaseModel):
    by_status: Dict[str, int]
    by_specialty: Dict[str, int]
    upcoming_count: int


class AnalyticsAIResponse(BaseModel):
    total_sessions: int
    voice_sessions: int
    capabilities_invoked: Dict[str, int]
    safety_escalations: int
