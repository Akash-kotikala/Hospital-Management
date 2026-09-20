from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import EntityNotFoundException, AppException
from app.db.models.doctor import Doctor, Calendar, Availability, BlockedSlot
from app.db.models.hospital import Hospital
from app.db.models.enums import DoctorStatus, HospitalStatus
from app.schemas.doctor import DoctorCreate, DoctorUpdate, AvailabilityCreate, BlockedSlotCreate
from app.services.audit_service import AuditService


class DoctorService:
    @staticmethod
    async def create_doctor(db: AsyncSession, doctor_in: DoctorCreate) -> Doctor:
        # Verify hospital is approved
        hospital = await db.get(Hospital, doctor_in.hospital_id)
        if not hospital:
            raise EntityNotFoundException("Hospital", doctor_in.hospital_id)
        if hospital.status != HospitalStatus.APPROVED:
            raise AppException(
                code="HOSPITAL_NOT_APPROVED",
                message=f"Cannot create doctor for hospital '{hospital.name}' with status '{hospital.status.value}'. Must be APPROVED."
            )

        doctor = Doctor(
            name=doctor_in.name,
            hospital_id=doctor_in.hospital_id,
            specialty_id=doctor_in.specialty_id,
            department_id=doctor_in.department_id,
            qualifications=doctor_in.qualifications,
            experience_years=doctor_in.experience_years,
            languages=doctor_in.languages,
            consultation_types=doctor_in.consultation_types,
            appointment_duration_minutes=doctor_in.appointment_duration_minutes,
            bio=doctor_in.bio,
            user_id=doctor_in.user_id,
            external_provider_id=doctor_in.external_provider_id,
            status=DoctorStatus.ACTIVE,
        )
        db.add(doctor)
        await db.flush()

        # Initialize doctor calendar
        calendar = Calendar(
            doctor_id=doctor.id,
            hospital_id=doctor.hospital_id,
            timezone="UTC",
            is_active=True,
        )
        db.add(calendar)
        await db.flush()

        await AuditService.log_audit_event(
            db=db,
            action="DOCTOR_CREATED",
            resource_type="DOCTOR",
            resource_id=doctor.id,
            hospital_id=doctor.hospital_id,
            details={"name": doctor.name, "specialty_id": doctor.specialty_id}
        )
        return doctor

    @staticmethod
    async def get_doctor(db: AsyncSession, doctor_id: str) -> Doctor:
        result = await db.execute(
            select(Doctor)
            .options(
                selectinload(Doctor.calendar).selectinload(Calendar.availabilities),
                selectinload(Doctor.blocked_slots),
                selectinload(Doctor.specialty),
                selectinload(Doctor.department),
            )
            .where(Doctor.id == doctor_id)
        )
        doctor = result.scalar_one_or_none()
        if not doctor:
            raise EntityNotFoundException("Doctor", doctor_id)
        return doctor

    @staticmethod
    async def list_doctors(
        db: AsyncSession,
        hospital_id: Optional[str] = None,
        specialty_id: Optional[str] = None,
        status: Optional[DoctorStatus] = None,
        search_query: Optional[str] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> List[Doctor]:
        query = (
            select(Doctor)
            .options(
                selectinload(Doctor.calendar).selectinload(Calendar.availabilities),
                selectinload(Doctor.specialty),
                selectinload(Doctor.department),
            )
            .offset(skip)
            .limit(limit)
        )
        if hospital_id:
            query = query.where(Doctor.hospital_id == hospital_id)
        if specialty_id:
            query = query.where(Doctor.specialty_id == specialty_id)
        if status:
            query = query.where(Doctor.status == status)
        if search_query:
            query = query.where(Doctor.name.ilike(f"%{search_query}%"))

        result = await db.execute(query)
        return list(result.scalars().all())

    @staticmethod
    async def add_availability(
        db: AsyncSession,
        doctor_id: str,
        avail_in: AvailabilityCreate,
    ) -> Availability:
        doctor = await DoctorService.get_doctor(db, doctor_id)
        if not doctor.calendar:
            calendar = Calendar(doctor_id=doctor.id, hospital_id=doctor.hospital_id, timezone="UTC", is_active=True)
            db.add(calendar)
            await db.flush()
            doctor.calendar = calendar

        availability = Availability(
            calendar_id=doctor.calendar.id,
            hospital_id=doctor.hospital_id,
            day_of_week=avail_in.day_of_week,
            start_time=avail_in.start_time,
            end_time=avail_in.end_time,
            slot_duration_minutes=avail_in.slot_duration_minutes,
            is_active=True,
        )
        db.add(availability)
        await db.flush()
        return availability

    @staticmethod
    async def add_blocked_slot(
        db: AsyncSession,
        doctor_id: str,
        block_in: BlockedSlotCreate,
    ) -> BlockedSlot:
        doctor = await DoctorService.get_doctor(db, doctor_id)
        blocked = BlockedSlot(
            doctor_id=doctor.id,
            hospital_id=doctor.hospital_id,
            start_time=block_in.start_time,
            end_time=block_in.end_time,
            reason=block_in.reason,
            is_all_day=block_in.is_all_day,
        )
        db.add(blocked)
        await db.flush()
        return blocked
