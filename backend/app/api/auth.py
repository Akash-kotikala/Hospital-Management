from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.database import get_db
from app.services.auth_service import AuthService
from app.schemas.auth import UserCreate, UserLogin, UserResponse, TokenResponse
from app.schemas.common import ApiResponse
from app.api.deps import get_current_user
from app.db.models.auth import User

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=ApiResponse[UserResponse], status_code=status.HTTP_201_CREATED)
async def register(user_in: UserCreate, db: AsyncSession = Depends(get_db)):
    """Register a new patient, hospital administrator, or doctor."""
    user = await AuthService.register_user(db, user_in)
    return ApiResponse(success=True, data=user)


@router.post("/login", response_model=ApiResponse[TokenResponse])
async def login(login_data: UserLogin, db: AsyncSession = Depends(get_db)):
    """Authenticate with email and password to receive JWT access token."""
    token_resp = await AuthService.authenticate_user(db, login_data)
    return ApiResponse(success=True, data=token_resp)


@router.get("/me", response_model=ApiResponse[UserResponse])
async def get_me(current_user: User = Depends(get_current_user)):
    """Retrieve currently authenticated user profile and roles."""
    hospital_id = current_user.staff_profile.hospital_id if current_user.staff_profile else None
    patient_id = current_user.patient_profile.id if current_user.patient_profile else None
    doctor_id = current_user.doctor_profile.id if current_user.doctor_profile else None

    resp = UserResponse(
        id=current_user.id,
        email=current_user.email,
        full_name=current_user.full_name,
        role=current_user.role,
        is_active=current_user.is_active,
        phone=current_user.phone,
        hospital_id=hospital_id,
        patient_id=patient_id,
        doctor_id=doctor_id,
    )
    return ApiResponse(success=True, data=resp)
