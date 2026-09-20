import datetime
from typing import Optional, List
from pydantic import BaseModel, Field
from app.db.models.enums import DoctorStatus, ConsultationType


class AvailabilityCreate(BaseModel):
    day_of_week: int = Field(ge=0, le=6, description="0=Monday, 6=Sunday")
    start_time: str = Field(pattern=r"^\d{2}:\d{2}$", description="HH:MM format, e.g. 09:00")
    end_time: str = Field(pattern=r"^\d{2}:\d{2}$", description="HH:MM format, e.g. 17:00")
    slot_duration_minutes: int = Field(default=30, ge=10, le=120)


class AvailabilityResponse(BaseModel):
    id: str
    calendar_id: str
    hospital_id: str
    day_of_week: int
    start_time: str
    end_time: str
    slot_duration_minutes: int
    is_active: bool

    model_config = {"from_attributes": True}


class BlockedSlotCreate(BaseModel):
    start_time: datetime.datetime
    end_time: datetime.datetime
    reason: Optional[str] = None
    is_all_day: bool = False


class BlockedSlotResponse(BaseModel):
    id: str
    doctor_id: str
    hospital_id: str
    start_time: datetime.datetime
    end_time: datetime.datetime
    reason: Optional[str] = None
    is_all_day: bool

    model_config = {"from_attributes": True}


class CalendarResponse(BaseModel):
    id: str
    doctor_id: str
    hospital_id: str
    timezone: str
    is_active: bool
    availabilities: List[AvailabilityResponse] = []

    model_config = {"from_attributes": True}


class DoctorCreate(BaseModel):
    name: str
    hospital_id: str
    specialty_id: Optional[str] = None
    department_id: Optional[str] = None
    qualifications: str = "MD"
    experience_years: int = 5
    languages: List[str] = ["English"]
    consultation_types: List[str] = ["IN_PERSON", "VIDEO"]
    appointment_duration_minutes: int = 30
    bio: Optional[str] = None
    user_id: Optional[str] = None
    external_provider_id: Optional[str] = None


class DoctorUpdate(BaseModel):
    name: Optional[str] = None
    specialty_id: Optional[str] = None
    department_id: Optional[str] = None
    qualifications: Optional[str] = None
    experience_years: Optional[int] = None
    languages: Optional[List[str]] = None
    consultation_types: Optional[List[str]] = None
    appointment_duration_minutes: Optional[int] = None
    status: Optional[DoctorStatus] = None
    bio: Optional[str] = None


class DoctorResponse(BaseModel):
    id: str
    name: str
    hospital_id: str
    specialty_id: Optional[str] = None
    department_id: Optional[str] = None
    qualifications: str
    experience_years: int
    languages: List[str]
    consultation_types: List[str]
    appointment_duration_minutes: int
    status: DoctorStatus
    bio: Optional[str] = None
    external_provider_id: Optional[str] = None
    calendar: Optional[CalendarResponse] = None

    model_config = {"from_attributes": True}


class AvailableSlot(BaseModel):
    doctor_id: str
    doctor_name: str
    hospital_id: str
    hospital_name: Optional[str] = None
    specialty_name: Optional[str] = None
    start_time: datetime.datetime
    end_time: datetime.datetime
    duration_minutes: int
    consultation_types: List[str]
