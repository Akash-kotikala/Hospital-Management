import pytest
import datetime
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.hospital import Hospital
from app.db.models.doctor import Doctor, Calendar, Availability, BlockedSlot
from app.db.models.appointment import Appointment
from app.db.models.enums import HospitalStatus, DoctorStatus, AppointmentStatus, ConsultationType
from app.services.scheduling_service import SchedulingService
from app.core.exceptions import SlotUnavailableException


@pytest.mark.asyncio
async def test_scheduling_real_availability(db_session: AsyncSession):
    # 1. Create Hospital & Doctor
    hosp = Hospital(name="St. Jude", slug="st-jude", address="City", phone="123", email="info@jude.org", status=HospitalStatus.APPROVED)
    db_session.add(hosp)
    await db_session.flush()

    doc = Doctor(
        name="Dr. Test",
        hospital_id=hosp.id,
        appointment_duration_minutes=30,
        consultation_types=["IN_PERSON"],
        status=DoctorStatus.ACTIVE,
    )
    db_session.add(doc)
    await db_session.flush()

    cal = Calendar(doctor_id=doc.id, hospital_id=hosp.id, is_active=True)
    db_session.add(cal)
    await db_session.flush()

    # Monday availability: 09:00 to 11:00 (4 x 30min slots: 09:00, 09:30, 10:00, 10:30)
    avail = Availability(calendar_id=cal.id, hospital_id=hosp.id, day_of_week=0, start_time="09:00", end_time="11:00", slot_duration_minutes=30, is_active=True)
    db_session.add(avail)
    await db_session.flush()

    # Test Monday date
    mon_date = datetime.date(2026, 9, 21)  # 2026-09-21 is Monday (weekday=0)

    slots = await SchedulingService.get_available_slots(db_session, doctor_id=doc.id, start_date=mon_date, end_date=mon_date)
    assert len(slots) == 4
    assert slots[0].start_time.hour == 9
    assert slots[0].start_time.minute == 0
    assert slots[3].start_time.hour == 10
    assert slots[3].start_time.minute == 30

    # 2. Add BlockedSlot from 09:30 to 10:30 (should remove 09:30 and 10:00 slots)
    b_start = datetime.datetime.combine(mon_date, datetime.time(9, 30), tzinfo=datetime.timezone.utc)
    b_end = datetime.datetime.combine(mon_date, datetime.time(10, 30), tzinfo=datetime.timezone.utc)
    blocked = BlockedSlot(doctor_id=doc.id, hospital_id=hosp.id, start_time=b_start, end_time=b_end, reason="Surgery")
    db_session.add(blocked)
    await db_session.flush()

    slots_after_block = await SchedulingService.get_available_slots(db_session, doctor_id=doc.id, start_date=mon_date, end_date=mon_date)
    assert len(slots_after_block) == 2  # Only 09:00 and 10:30 remain


@pytest.mark.asyncio
async def test_slot_revalidation_prevents_conflict(db_session: AsyncSession):
    hosp = Hospital(name="Apex", slug="apex", address="City", phone="123", email="info@apex.org", status=HospitalStatus.APPROVED)
    db_session.add(hosp)
    await db_session.flush()

    doc = Doctor(name="Dr. Conflict", hospital_id=hosp.id, status=DoctorStatus.ACTIVE)
    db_session.add(doc)
    await db_session.flush()

    # Book existing appointment
    t_start = datetime.datetime(2026, 9, 21, 10, 0, tzinfo=datetime.timezone.utc)
    t_end = datetime.datetime(2026, 9, 21, 10, 30, tzinfo=datetime.timezone.utc)

    appt = Appointment(
        hospital_id=hosp.id,
        patient_id="dummy-pat",
        doctor_id=doc.id,
        start_time=t_start,
        end_time=t_end,
        status=AppointmentStatus.CONFIRMED,
    )
    db_session.add(appt)
    await db_session.flush()

    # Revalidation for conflicting slot must raise SlotUnavailableException
    with pytest.raises(SlotUnavailableException):
        await SchedulingService.revalidate_slot_availability(db_session, doc.id, t_start, t_end)
