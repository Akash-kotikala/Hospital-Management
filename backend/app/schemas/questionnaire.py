import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from app.db.models.enums import QuestionType


class QuestionCreate(BaseModel):
    prompt: str
    question_type: QuestionType = QuestionType.SHORT_TEXT
    options: List[str] = Field(default_factory=list)
    is_required: bool = True
    order_index: int = 0
    validation_rules: Dict[str, Any] = Field(default_factory=dict)


class QuestionResponse(BaseModel):
    id: str
    questionnaire_id: str
    prompt: str
    question_type: QuestionType
    options: List[str] = []
    is_required: bool
    order_index: int

    model_config = {"from_attributes": True}


class QuestionnaireCreate(BaseModel):
    hospital_id: str
    title: str
    description: Optional[str] = None
    specialty_id: Optional[str] = None
    doctor_id: Optional[str] = None
    questions: List[QuestionCreate] = []


class QuestionnaireResponseModel(BaseModel):
    id: str
    hospital_id: str
    title: str
    description: Optional[str] = None
    specialty_id: Optional[str] = None
    doctor_id: Optional[str] = None
    is_active: bool
    questions: List[QuestionResponse] = []

    model_config = {"from_attributes": True}


class QuestionnaireAnswerSubmit(BaseModel):
    appointment_id: str
    answers: Dict[str, Any]  # {question_id_or_prompt: answer_value}
    is_completed: bool = True


class DoctorReviewSubmit(BaseModel):
    doctor_notes: str


class QuestionnaireSubmissionResponse(BaseModel):
    id: str
    questionnaire_id: str
    appointment_id: str
    patient_id: str
    answers: Dict[str, Any]
    is_completed: bool
    completed_at: Optional[datetime.datetime] = None
    reviewed_by_doctor_id: Optional[str] = None
    reviewed_at: Optional[datetime.datetime] = None
    doctor_notes: Optional[str] = None

    model_config = {"from_attributes": True}
