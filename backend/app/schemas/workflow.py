import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from app.db.models.enums import WorkflowStatus


class WorkflowCreate(BaseModel):
    name: str
    hospital_id: str
    event_trigger: str
    conditions: Dict[str, Any] = Field(default_factory=dict)
    actions: List[Dict[str, Any]] = Field(default_factory=list)
    is_active: bool = True


class WorkflowResponse(BaseModel):
    id: str
    hospital_id: str
    name: str
    event_trigger: str
    conditions: Dict[str, Any]
    actions: List[Dict[str, Any]]
    is_active: bool

    model_config = {"from_attributes": True}


class WorkflowExecutionResponse(BaseModel):
    id: str
    workflow_id: str
    hospital_id: str
    trigger_event: str
    status: WorkflowStatus
    current_step: int
    result: Dict[str, Any]
    retry_count: int
    error_message: Optional[str] = None
    created_at: datetime.datetime

    model_config = {"from_attributes": True}


class NotificationResponse(BaseModel):
    id: str
    hospital_id: str
    channel: str
    recipient: str
    subject: str
    content: str
    status: str
    created_at: datetime.datetime

    model_config = {"from_attributes": True}
