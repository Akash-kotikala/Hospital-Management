from typing import List, Optional
from fastapi import APIRouter, Depends, status, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.db.models.auth import User
from app.db.models.enums import UserRole, HospitalStatus
from app.api.deps import get_current_user, require_role, verify_tenant_access
from app.services.hospital_service import HospitalService
from app.schemas.hospital import (
    HospitalCreate,
    HospitalUpdate,
    HospitalResponse,
    DepartmentCreate,
    DepartmentResponse,
    SpecialtyCreate,
    SpecialtyResponse,
)
from app.schemas.common import ApiResponse

router = APIRouter(prefix="/hospitals", tags=["Hospitals & Multi-Tenancy"])


@router.post("", response_model=ApiResponse[HospitalResponse], status_code=status.HTTP_201_CREATED)
async def create_hospital(
    hospital_in: HospitalCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.PLATFORM_ADMIN, UserRole.HOSPITAL_ADMIN)),
):
    """Register a new hospital tenant."""
    hospital = await HospitalService.create_hospital(db, hospital_in)
    return ApiResponse(success=True, data=hospital)


@router.get("", response_model=ApiResponse[List[HospitalResponse]])
async def list_hospitals(
    status: Optional[HospitalStatus] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """List hospitals. Public directory for approved hospitals, admin view for all statuses."""
    hospitals = await HospitalService.list_hospitals(db, status=status, skip=skip, limit=limit)
    return ApiResponse(success=True, data=hospitals)


@router.get("/{id}", response_model=ApiResponse[HospitalResponse])
async def get_hospital(id: str, db: AsyncSession = Depends(get_db)):
    """Retrieve hospital tenant by ID."""
    hospital = await HospitalService.get_hospital(db, id)
    return ApiResponse(success=True, data=hospital)


@router.put("/{id}", response_model=ApiResponse[HospitalResponse])
async def update_hospital(
    id: str,
    hospital_in: HospitalUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.PLATFORM_ADMIN, UserRole.HOSPITAL_ADMIN)),
):
    """Update hospital settings. Enforces tenant authorization."""
    await verify_tenant_access(id, current_user)
    hospital = await HospitalService.get_hospital(db, id)
    if hospital_in.name:
        hospital.name = hospital_in.name
    if hospital_in.address:
        hospital.address = hospital_in.address
    if hospital_in.phone:
        hospital.phone = hospital_in.phone
    if hospital_in.email:
        hospital.email = hospital_in.email
    if hospital_in.configuration:
        hospital.configuration.update(hospital_in.configuration)
    await db.flush()
    return ApiResponse(success=True, data=hospital)


@router.post("/{id}/submit", response_model=ApiResponse[HospitalResponse])
async def submit_hospital(
    id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.PLATFORM_ADMIN, UserRole.HOSPITAL_ADMIN)),
):
    """Submit hospital application for Platform Admin onboarding approval."""
    await verify_tenant_access(id, current_user)
    hospital = await HospitalService.submit_hospital(db, id)
    return ApiResponse(success=True, data=hospital)


@router.post("/{id}/approve", response_model=ApiResponse[HospitalResponse])
async def approve_hospital(
    id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.PLATFORM_ADMIN)),
):
    """Platform Admin approval of hospital onboarding."""
    hospital = await HospitalService.approve_hospital(db, id, admin_user_id=current_user.id)
    return ApiResponse(success=True, data=hospital)


@router.post("/{id}/reject", response_model=ApiResponse[HospitalResponse])
async def reject_hospital(
    id: str,
    reason: str = Query("Did not meet requirements"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.PLATFORM_ADMIN)),
):
    """Platform Admin rejection of hospital onboarding."""
    hospital = await HospitalService.reject_hospital(db, id, admin_user_id=current_user.id, reason=reason)
    return ApiResponse(success=True, data=hospital)


@router.post("/{id}/departments", response_model=ApiResponse[DepartmentResponse], status_code=status.HTTP_201_CREATED)
async def add_department(
    id: str,
    dept_in: DepartmentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.PLATFORM_ADMIN, UserRole.HOSPITAL_ADMIN)),
):
    await verify_tenant_access(id, current_user)
    dept = await HospitalService.add_department(db, id, dept_in)
    return ApiResponse(success=True, data=dept)


@router.post("/{id}/specialties", response_model=ApiResponse[SpecialtyResponse], status_code=status.HTTP_201_CREATED)
async def add_specialty(
    id: str,
    spec_in: SpecialtyCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.PLATFORM_ADMIN, UserRole.HOSPITAL_ADMIN)),
):
    await verify_tenant_access(id, current_user)
    spec = await HospitalService.add_specialty(db, id, spec_in)
    return ApiResponse(success=True, data=spec)
