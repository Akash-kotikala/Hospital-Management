from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.database import get_db
from app.db.models.auth import User
from app.db.models.patient import Patient, UserPreference
from app.api.deps import get_current_user
from app.schemas.patient import PatientCreate, PatientUpdate, PatientResponse, UserPreferenceCreate, UserPreferenceResponse
from app.schemas.common import ApiResponse
from app.core.exceptions import EntityNotFoundException

router = APIRouter(prefix="/patients", tags=["Patients"])


@router.post("", response_model=ApiResponse[PatientResponse], status_code=status.HTTP_201_CREATED)
async def create_patient(
    patient_in: PatientCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    patient = Patient(
        user_id=current_user.id,
        first_name=patient_in.first_name,
        last_name=patient_in.last_name,
        phone=patient_in.phone,
        email=patient_in.email,
        date_of_birth=patient_in.date_of_birth,
        gender=patient_in.gender,
        address=patient_in.address,
        insurance_info=patient_in.insurance_info or {},
        emergency_contact=patient_in.emergency_contact or {},
        primary_hospital_id=patient_in.primary_hospital_id,
    )
    db.add(patient)
    await db.flush()
    return ApiResponse(success=True, data=patient)


@router.get("/me", response_model=ApiResponse[PatientResponse])
async def get_patient_profile(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(Patient).where(Patient.user_id == current_user.id))
    patient = result.scalar_one_or_none()
    if not patient:
        # Auto-create basic patient profile if not exists
        names = current_user.full_name.split(" ", 1)
        patient = Patient(
            user_id=current_user.id,
            first_name=names[0],
            last_name=names[1] if len(names) > 1 else "",
            email=current_user.email,
            phone=current_user.phone or "Unknown",
        )
        db.add(patient)
        await db.flush()
    return ApiResponse(success=True, data=patient)


@router.put("/me", response_model=ApiResponse[PatientResponse])
async def update_patient_profile(
    patient_in: PatientUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(Patient).where(Patient.user_id == current_user.id))
    patient = result.scalar_one_or_none()
    if not patient:
        raise EntityNotFoundException("Patient", current_user.id)

    for field, val in patient_in.model_dump(exclude_unset=True).items():
        setattr(patient, field, val)

    await db.flush()
    return ApiResponse(success=True, data=patient)
