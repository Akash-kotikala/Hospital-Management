from typing import List, Optional
from fastapi import APIRouter, Depends, status, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.db.models.auth import User
from app.db.models.enums import UserRole, DoctorStatus
from app.api.deps import get_current_user, require_role, verify_tenant_access
from app.services.doctor_service import DoctorService
from app.schemas.doctor import DoctorCreate, DoctorUpdate, DoctorResponse
from app.schemas.common import ApiResponse

router = APIRouter(prefix="/doctors", tags=["Doctors"])


@router.post("", response_model=ApiResponse[DoctorResponse], status_code=status.HTTP_201_CREATED)
async def create_doctor(
    doctor_in: DoctorCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.PLATFORM_ADMIN, UserRole.HOSPITAL_ADMIN)),
):
    """Create a new doctor within an approved hospital."""
    await verify_tenant_access(doctor_in.hospital_id, current_user)
    doctor = await DoctorService.create_doctor(db, doctor_in)
    return ApiResponse(success=True, data=doctor)


@router.get("", response_model=ApiResponse[List[DoctorResponse]])
async def list_doctors(
    hospital_id: Optional[str] = None,
    specialty_id: Optional[str] = None,
    status: Optional[DoctorStatus] = None,
    search: Optional[str] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """List doctors with optional filtering by hospital, specialty, status, or search term."""
    doctors = await DoctorService.list_doctors(
        db,
        hospital_id=hospital_id,
        specialty_id=specialty_id,
        status=status,
        search_query=search,
        skip=skip,
        limit=limit,
    )
    return ApiResponse(success=True, data=doctors)


@router.get("/{id}", response_model=ApiResponse[DoctorResponse])
async def get_doctor(id: str, db: AsyncSession = Depends(get_db)):
    """Retrieve full doctor profile with calendar and specialty details."""
    doctor = await DoctorService.get_doctor(db, id)
    return ApiResponse(success=True, data=doctor)


@router.put("/{id}", response_model=ApiResponse[DoctorResponse])
async def update_doctor(
    id: str,
    doctor_in: DoctorUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.PLATFORM_ADMIN, UserRole.HOSPITAL_ADMIN, UserRole.DOCTOR)),
):
    """Update doctor qualifications, languages, or status."""
    doctor = await DoctorService.get_doctor(db, id)
    await verify_tenant_access(doctor.hospital_id, current_user)

    for field, val in doctor_in.model_dump(exclude_unset=True).items():
        setattr(doctor, field, val)

    await db.flush()
    return ApiResponse(success=True, data=doctor)
