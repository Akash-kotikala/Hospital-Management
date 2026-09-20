import datetime
from typing import List, Optional
from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import EntityNotFoundException, SlotUnavailableException
from app.db.models.doctor import Doctor, Calendar, Availability, BlockedSlot
from app.db.models.appointment import Appointment
from app.db.models.enums import DoctorStatus, AppointmentStatus
from app.schemas.doctor import AvailableSlot


def _ensure_utc(dt: datetime.datetime) -> datetime.datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=datetime.timezone.utc)
    return dt.astimezone(datetime.timezone.utc)


class SchedulingService:
    @staticmethod
    async def get_available_slots(
        db: AsyncSession,
        doctor_id: str,
        start_date: datetime.date,
        end_date: datetime.date,
        consultation_type: Optional[str] = None,
    ) -> List[AvailableSlot]:
        """Calculates real available slots strictly backed by database schedules and constraints."""
        # 1. Fetch Doctor and check active status
        doctor_query = await db.execute(
            select(Doctor)
            .options(
                selectinload(Doctor.calendar).selectinload(Calendar.availabilities),
                selectinload(Doctor.hospital),
                selectinload(Doctor.specialty),
            )
            .where(Doctor.id == doctor_id)
        )
        doctor = doctor_query.scalar_one_or_none()
        if not doctor:
            raise EntityNotFoundException("Doctor", doctor_id)

        if doctor.status != DoctorStatus.ACTIVE or not doctor.calendar or not doctor.calendar.is_active:
            return []

        if consultation_type and consultation_type not in doctor.consultation_types:
            return []

        # 2. Fetch all BlockedSlots for the date range
        range_start_dt = datetime.datetime.combine(start_date, datetime.time.min, tzinfo=datetime.timezone.utc)
        range_end_dt = datetime.datetime.combine(end_date, datetime.time.max, tzinfo=datetime.timezone.utc)

        blocked_query = await db.execute(
            select(BlockedSlot).where(
                BlockedSlot.doctor_id == doctor_id,
                BlockedSlot.start_time <= range_end_dt,
                BlockedSlot.end_time >= range_start_dt,
            )
        )
        blocked_slots = list(blocked_query.scalars().all())

        # 3. Fetch existing booked / pending appointments
        active_statuses = [
            AppointmentStatus.PENDING,
            AppointmentStatus.CONFIRMED,
            AppointmentStatus.REQUESTED,
            AppointmentStatus.SYNCHRONIZATION_PENDING,
            AppointmentStatus.RECONCILIATION_REQUIRED,
        ]
        appts_query = await db.execute(
            select(Appointment).where(
                Appointment.doctor_id == doctor_id,
                Appointment.status.in_(active_statuses),
                Appointment.start_time <= range_end_dt,
                Appointment.end_time >= range_start_dt,
            )
        )
        existing_appointments = list(appts_query.scalars().all())

        # 4. Generate candidate slots from active availabilities
        active_availabilities = [a for a in doctor.calendar.availabilities if a.is_active]
        available_slots: List[AvailableSlot] = []

        curr_date = start_date
        duration = datetime.timedelta(minutes=doctor.appointment_duration_minutes)

        while curr_date <= end_date:
            weekday = curr_date.weekday()  # Monday is 0, Sunday is 6
            day_rules = [a for a in active_availabilities if a.day_of_week == weekday]

            for rule in day_rules:
                # Parse start and end time
                sh, sm = map(int, rule.start_time.split(":"))
                eh, em = map(int, rule.end_time.split(":"))
                slot_duration = datetime.timedelta(minutes=rule.slot_duration_minutes or doctor.appointment_duration_minutes)

                slot_start = datetime.datetime.combine(curr_date, datetime.time(sh, sm), tzinfo=datetime.timezone.utc)
                window_end = datetime.datetime.combine(curr_date, datetime.time(eh, em), tzinfo=datetime.timezone.utc)

                while slot_start + slot_duration <= window_end:
                    slot_end = slot_start + slot_duration

                    # Check conflict with blocked slots
                    is_blocked = any(
                        (_ensure_utc(b.start_time) < slot_end and _ensure_utc(b.end_time) > slot_start)
                        for b in blocked_slots
                    )

                    # Check conflict with existing appointments
                    is_booked = any(
                        (_ensure_utc(a.start_time) < slot_end and _ensure_utc(a.end_time) > slot_start)
                        for a in existing_appointments
                    )

                    if not is_blocked and not is_booked:
                        available_slots.append(
                            AvailableSlot(
                                doctor_id=doctor.id,
                                doctor_name=doctor.name,
                                hospital_id=doctor.hospital_id,
                                hospital_name=doctor.hospital.name if doctor.hospital else None,
                                specialty_name=doctor.specialty.name if doctor.specialty else None,
                                start_time=slot_start,
                                end_time=slot_end,
                                duration_minutes=int(slot_duration.total_seconds() / 60),
                                consultation_types=doctor.consultation_types,
                            )
                        )

                    slot_start += slot_duration

            curr_date += datetime.timedelta(days=1)

        return available_slots

    @staticmethod
    async def revalidate_slot_availability(
        db: AsyncSession,
        doctor_id: str,
        start_time: datetime.datetime,
        end_time: datetime.datetime,
        exclude_appointment_id: Optional[str] = None,
    ) -> bool:
        """Atomic revalidation immediately before booking or rescheduling."""
        # Check doctor status
        doctor = await db.get(Doctor, doctor_id)
        if not doctor or doctor.status != DoctorStatus.ACTIVE:
            raise SlotUnavailableException("Doctor is not currently active for scheduling.")

        # Check overlapping blocked slots
        blocked_query = select(BlockedSlot).where(
            BlockedSlot.doctor_id == doctor_id,
            BlockedSlot.start_time < end_time,
            BlockedSlot.end_time > start_time,
        )
        blocked_result = await db.execute(blocked_query)
        if blocked_result.scalars().first():
            raise SlotUnavailableException("The selected slot conflicts with a doctor blocked time.")

        # Check overlapping active appointments
        active_statuses = [
            AppointmentStatus.PENDING,
            AppointmentStatus.CONFIRMED,
            AppointmentStatus.REQUESTED,
            AppointmentStatus.SYNCHRONIZATION_PENDING,
            AppointmentStatus.RECONCILIATION_REQUIRED,
        ]
        appts_query = select(Appointment).where(
            Appointment.doctor_id == doctor_id,
            Appointment.status.in_(active_statuses),
            Appointment.start_time < end_time,
            Appointment.end_time > start_time,
        )
        if exclude_appointment_id:
            appts_query = appts_query.where(Appointment.id != exclude_appointment_id)

        appts_result = await db.execute(appts_query)
        conflict = appts_result.scalars().first()
        if conflict:
            raise SlotUnavailableException(
                f"The selected appointment slot {start_time.isoformat()} is already reserved or booked."
            )

        return True
