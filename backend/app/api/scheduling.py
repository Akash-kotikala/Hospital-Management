import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, status, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.db.models.auth import User
from app.db.models.enums import UserRole
from app.api.deps import get_current_user, require_role, verify_tenant_access
from app.services.doctor_service import DoctorService
from app.services.scheduling_service import SchedulingService
from app.schemas.doctor import (
    AvailabilityCreate,
    AvailabilityResponse,
    BlockedSlotCreate,
    BlockedSlotResponse,
    AvailableSlot,
)
from app.schemas.common import ApiResponse

router = APIRouter(prefix="/doctors", tags=["Scheduling & Availability"])


@router.post("/{id}/availability", response_model=ApiResponse[AvailabilityResponse], status_code=status.HTTP_201_CREATED)
async def add_doctor_availability(
    id: str,
    avail_in: AvailabilityCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.PLATFORM_ADMIN, UserRole.HOSPITAL_ADMIN, UserRole.DOCTOR)),
):
    """Add recurring working hours for a doctor's calendar."""
    doctor = await DoctorService.get_doctor(db, id)
    await verify_tenant_access(doctor.hospital_id, current_user)
    avail = await DoctorService.add_availability(db, id, avail_in)
    return ApiResponse(success=True, data=avail)


@router.get("/{id}/availability", response_model=ApiResponse[List[AvailabilityResponse]])
async def get_doctor_availability(id: str, db: AsyncSession = Depends(get_db)):
    """Retrieve configured weekly schedule for a doctor."""
    doctor = await DoctorService.get_doctor(db, id)
    avails = doctor.calendar.availabilities if doctor.calendar else []
    return ApiResponse(success=True, data=avails)


@router.post("/{id}/blocked-slots", response_model=ApiResponse[BlockedSlotResponse], status_code=status.HTTP_201_CREATED)
async def add_blocked_slot(
    id: str,
    block_in: BlockedSlotCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.PLATFORM_ADMIN, UserRole.HOSPITAL_ADMIN, UserRole.DOCTOR)),
):
    """Block a date/time window on a doctor's calendar (leave, surgery, personal time)."""
    doctor = await DoctorService.get_doctor(db, id)
    await verify_tenant_access(doctor.hospital_id, current_user)
    blocked = await DoctorService.add_blocked_slot(db, id, block_in)
    return ApiResponse(success=True, data=blocked)


@router.get("/{id}/slots", response_model=ApiResponse[List[AvailableSlot]])
async def get_doctor_available_slots(
    id: str,
    start_date: Optional[datetime.date] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[datetime.date] = Query(None, description="End date (YYYY-MM-DD)"),
    consultation_type: Optional[str] = Query(None, description="IN_PERSON or VIDEO"),
    db: AsyncSession = Depends(get_db),
):
    """Real availability lookup: Computes genuine database-backed bookable slots."""
    today = datetime.datetime.now(datetime.timezone.utc).date()
    s_date = start_date or today
    e_date = end_date or (s_date + datetime.timedelta(days=7))

    slots = await SchedulingService.get_available_slots(
        db=db,
        doctor_id=id,
        start_date=s_date,
        end_date=e_date,
        consultation_type=consultation_type,
    )
    return ApiResponse(success=True, data=slots)
