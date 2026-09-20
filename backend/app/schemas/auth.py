from typing import Optional
from pydantic import BaseModel, EmailStr
from app.db.models.enums import UserRole


class UserCreate(BaseModel):
    email: EmailStr
    password: str
    full_name: str
    role: UserRole = UserRole.PATIENT
    phone: Optional[str] = None
    hospital_id: Optional[str] = None  # If registering as hospital admin or doctor


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    id: str
    email: str
    full_name: str
    role: UserRole
    is_active: bool
    phone: Optional[str] = None
    hospital_id: Optional[str] = None  # Scoped hospital if staff/doctor
    patient_id: Optional[str] = None
    doctor_id: Optional[str] = None

    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse
