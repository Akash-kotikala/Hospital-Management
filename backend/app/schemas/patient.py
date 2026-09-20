import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel, EmailStr


class PatientCreate(BaseModel):
    first_name: str
    last_name: str
    phone: str
    email: EmailStr
    date_of_birth: Optional[datetime.date] = None
    gender: Optional[str] = None
    address: Optional[str] = None
    insurance_info: Optional[Dict[str, Any]] = None
    emergency_contact: Optional[Dict[str, Any]] = None
    primary_hospital_id: Optional[str] = None


class PatientUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[EmailStr] = None
    date_of_birth: Optional[datetime.date] = None
    gender: Optional[str] = None
    address: Optional[str] = None
    insurance_info: Optional[Dict[str, Any]] = None
    emergency_contact: Optional[Dict[str, Any]] = None
    primary_hospital_id: Optional[str] = None


class PatientResponse(BaseModel):
    id: str
    user_id: Optional[str] = None
    first_name: str
    last_name: str
    phone: str
    email: str
    date_of_birth: Optional[datetime.date] = None
    gender: Optional[str] = None
    address: Optional[str] = None
    insurance_info: Dict[str, Any]
    emergency_contact: Dict[str, Any]
    external_patient_id: Optional[str] = None
    primary_hospital_id: Optional[str] = None

    model_config = {"from_attributes": True}


class UserPreferenceCreate(BaseModel):
    preferred_hospital_id: Optional[str] = None
    preferred_communication_channel: str = "EMAIL"
    language: str = "en"
    notification_opt_in: bool = True
    notes: Optional[str] = None


class UserPreferenceResponse(BaseModel):
    id: str
    user_id: str
    preferred_hospital_id: Optional[str] = None
    preferred_communication_channel: str
    language: str
    notification_opt_in: bool
    notes: Optional[str] = None

    model_config = {"from_attributes": True}
