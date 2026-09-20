import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from app.db.models.enums import HospitalStatus


class DepartmentCreate(BaseModel):
    name: str
    code: str
    description: Optional[str] = None


class DepartmentResponse(BaseModel):
    id: str
    hospital_id: str
    name: str
    code: str
    description: Optional[str] = None

    model_config = {"from_attributes": True}


class SpecialtyCreate(BaseModel):
    name: str
    code: str
    description: Optional[str] = None


class SpecialtyResponse(BaseModel):
    id: str
    hospital_id: Optional[str] = None
    name: str
    code: str
    description: Optional[str] = None

    model_config = {"from_attributes": True}


class HospitalCreate(BaseModel):
    name: str
    slug: str
    address: str
    phone: str
    email: str
    website: Optional[str] = None
    configuration: Optional[Dict[str, Any]] = Field(default_factory=dict)


class HospitalUpdate(BaseModel):
    name: Optional[str] = None
    address: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    website: Optional[str] = None
    configuration: Optional[Dict[str, Any]] = None


class HospitalResponse(BaseModel):
    id: str
    name: str
    slug: str
    address: str
    phone: str
    email: str
    website: Optional[str] = None
    status: HospitalStatus
    configuration: Dict[str, Any]
    created_at: datetime.datetime
    departments: List[DepartmentResponse] = []
    specialties: List[SpecialtyResponse] = []

    model_config = {"from_attributes": True}
