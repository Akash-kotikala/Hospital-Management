from typing import List, Optional
from fastapi import APIRouter, Depends, status, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.db.models.auth import User
from app.db.models.patient import Patient
from app.db.models.enums import UserRole, AppointmentStatus
from app.api.deps import get_current_user, require_role, verify_tenant_access
from app.services.appointment_service import AppointmentService
from app.schemas.appointment import (
    AppointmentCreate,
    AppointmentReschedule,
    AppointmentCancel,
    AppointmentResponse,
)
from app.schemas.common import ApiResponse
from app.core.exceptions import EntityNotFoundException, AuthorizationException

router = APIRouter(prefix="/appointments", tags=["Appointments & Booking"])


@router.post("", response_model=ApiResponse[AppointmentResponse], status_code=status.HTTP_201_CREATED)
async def create_appointment(
    appt_in: AppointmentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Executes the full booking lifecycle:
    1. Availability revalidation
    2. Internal appointment (PENDING)
    3. Idempotency tracking
    4. Call EHR connector
    5. Two-phase verification
    6. Internal synchronization (CONFIRMED)
    7. Post-booking workflow & notification
    """
    patient_id = appt_in.patient_id
    if not patient_id:
        # Resolve patient from current user
        pat_res = await db.execute(select(Patient).where(Patient.user_id == current_user.id))
        pat = pat_res.scalar_one_or_none()
        if not pat:
            # Auto-create patient record
            names = current_user.full_name.split(" ", 1)
            pat = Patient(
                user_id=current_user.id,
                first_name=names[0],
                last_name=names[1] if len(names) > 1 else "",
                email=current_user.email,
                phone=current_user.phone or "Unknown",
            )
            db.add(pat)
            await db.flush()
        patient_id = pat.id

    result = await AppointmentService.book_appointment(
        db=db,
        appt_in=appt_in,
        patient_id=patient_id,
        user_id=current_user.id,
    )
    appointment = result["appointment"]
    # Re-fetch with relationships
    full_appt = await AppointmentService.get_appointment(db, appointment.id)
    return ApiResponse(success=True, data=full_appt)


@router.get("", response_model=ApiResponse[List[AppointmentResponse]])
async def list_appointments(
    hospital_id: Optional[str] = None,
    doctor_id: Optional[str] = None,
    status: Optional[AppointmentStatus] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List appointments with strict multi-tenant and role scoping."""
    scoped_hospital_id = hospital_id
    scoped_doctor_id = doctor_id
    scoped_patient_id = None

    if current_user.role == UserRole.PATIENT:
        if current_user.patient_profile:
            scoped_patient_id = current_user.patient_profile.id
    elif current_user.role == UserRole.DOCTOR:
        if current_user.doctor_profile:
            scoped_doctor_id = current_user.doctor_profile.id
            scoped_hospital_id = current_user.doctor_profile.hospital_id
    elif current_user.role == UserRole.HOSPITAL_ADMIN:
        if current_user.staff_profile:
            scoped_hospital_id = current_user.staff_profile.hospital_id

    appts = await AppointmentService.list_appointments(
        db=db,
        hospital_id=scoped_hospital_id,
        doctor_id=scoped_doctor_id,
        patient_id=scoped_patient_id,
        status=status,
        skip=skip,
        limit=limit,
    )
    return ApiResponse(success=True, data=appts)


@router.get("/{id}", response_model=ApiResponse[AppointmentResponse])
async def get_appointment(
    id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get appointment with full lifecycle transition history."""
    appt = await AppointmentService.get_appointment(db, id)

    # Tenant and patient authorization check
    if current_user.role == UserRole.PATIENT:
        if appt.patient.user_id != current_user.id:
            raise AuthorizationException("Cannot access another patient's appointment.")
    elif current_user.role in (UserRole.HOSPITAL_ADMIN, UserRole.DOCTOR):
        await verify_tenant_access(appt.hospital_id, current_user)

    return ApiResponse(success=True, data=appt)


@router.post("/{id}/reschedule", response_model=ApiResponse[AppointmentResponse])
async def reschedule_appointment(
    id: str,
    resched_in: AppointmentReschedule,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Reschedule an existing appointment with EHR synchronization and slot reservation."""
    appt = await AppointmentService.get_appointment(db, id)
    if current_user.role == UserRole.PATIENT and appt.patient.user_id != current_user.id:
        raise AuthorizationException("Cannot reschedule another patient's appointment.")

    rescheduled = await AppointmentService.reschedule_appointment(
        db=db, appointment_id=id, reschedule_in=resched_in, user_id=current_user.id
    )
    full_appt = await AppointmentService.get_appointment(db, rescheduled.id)
    return ApiResponse(success=True, data=full_appt)


@router.post("/{id}/cancel", response_model=ApiResponse[AppointmentResponse])
async def cancel_appointment(
    id: str,
    cancel_in: AppointmentCancel,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Cancel an appointment, release slot, and notify provider/patient."""
    appt = await AppointmentService.get_appointment(db, id)
    if current_user.role == UserRole.PATIENT and appt.patient.user_id != current_user.id:
        raise AuthorizationException("Cannot cancel another patient's appointment.")

    cancelled = await AppointmentService.cancel_appointment(
        db=db, appointment_id=id, cancel_in=cancel_in, user_id=current_user.id
    )
    full_appt = await AppointmentService.get_appointment(db, cancelled.id)
    return ApiResponse(success=True, data=full_appt)
