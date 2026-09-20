import pytest
import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.models.hospital import Hospital
from app.db.models.doctor import Doctor, Calendar, Availability
from app.db.models.patient import Patient
from app.db.models.appointment import Appointment
from app.db.models.integration import ReconciliationRecord
from app.db.models.enums import HospitalStatus, DoctorStatus, AppointmentStatus, EHRSimulationMode, ReconciliationStatus
from app.services.appointment_service import AppointmentService
from app.schemas.appointment import AppointmentCreate
from app.integrations.mock_ehr import mock_ehr_connector


@pytest.mark.asyncio
async def test_ehr_timeout_and_unknown_outcome_recovery(db_session: AsyncSession):
    # Setup test hospital, doctor, calendar, patient
    hosp = Hospital(name="Recovery Hospital", slug="rec-hosp", address="123 Care Way", phone="111", email="h@r.com", status=HospitalStatus.APPROVED)
    db_session.add(hosp)
    await db_session.flush()

    doc = Doctor(name="Dr. Recovery", hospital_id=hosp.id, appointment_duration_minutes=30, status=DoctorStatus.ACTIVE)
    db_session.add(doc)
    await db_session.flush()

    cal = Calendar(doctor_id=doc.id, hospital_id=hosp.id, is_active=True)
    db_session.add(cal)
    await db_session.flush()

    # Mon-Fri 08:00 - 18:00
    for day in range(5):
        db_session.add(Availability(calendar_id=cal.id, hospital_id=hosp.id, day_of_week=day, start_time="08:00", end_time="18:00", slot_duration_minutes=30, is_active=True))

    pat = Patient(first_name="Alice", last_name="Smith", email="alice@test.com", phone="555-0199")
    db_session.add(pat)
    await db_session.flush()

    # 1. Arm Mock EHR with UNKNOWN_OUTCOME simulation mode for the next CREATE_APPOINTMENT operation
    mock_ehr_connector.set_simulation_mode(
        mode=EHRSimulationMode.UNKNOWN_OUTCOME,
        target_operation="CREATE_APPOINTMENT",
        countdown=1,
    )

    # Next Monday 10:00
    start_time = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=1)
    start_time = start_time.replace(hour=10, minute=0, second=0, microsecond=0)

    appt_create = AppointmentCreate(
        doctor_id=doc.id,
        hospital_id=hosp.id,
        start_time=start_time,
        reason_for_visit="Knee checkup",
    )

    # 2. Execute booking: Should encounter timeout, initiate recovery, discover the record, and synchronize state
    result = await AppointmentService.book_appointment(
        db=db_session,
        appt_in=appt_create,
        patient_id=pat.id,
    )

    assert result["timeout_encountered"] is True
    assert result["status"] == AppointmentStatus.CONFIRMED.value
    assert result["recovery"]["recovered"] is True

    # 3. Verify internal appointment state in DB
    appointment = result["appointment"]
    assert appointment.status == AppointmentStatus.CONFIRMED
    assert appointment.external_appointment_id is not None
    assert appointment.external_appointment_id.startswith("EHR-APPT-")

    # 4. Verify reconciliation record was recorded as RESOLVED
    rec_query = await db_session.execute(
        select(ReconciliationRecord).where(ReconciliationRecord.appointment_id == appointment.id)
    )
    rec = rec_query.scalar_one_or_none()
    assert rec is not None
    assert rec.status == ReconciliationStatus.RESOLVED

    # 5. Prevent Duplicate Booking: Ensure calling again for same slot raises conflict
    with pytest.raises(Exception):
        await AppointmentService.book_appointment(
            db=db_session,
            appt_in=appt_create,
            patient_id=pat.id,
        )
