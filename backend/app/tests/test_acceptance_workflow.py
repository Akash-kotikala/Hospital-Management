import pytest
import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.models.hospital import Hospital, Specialty
from app.db.models.doctor import Doctor, Calendar, Availability
from app.db.models.patient import Patient
from app.db.models.appointment import Appointment
from app.db.models.questionnaire import Questionnaire, QuestionnaireQuestion, QuestionnaireResponse
from app.db.models.auth import User
from app.db.models.integration import ReconciliationRecord
from app.db.models.enums import HospitalStatus, DoctorStatus, AppointmentStatus, UserRole, QuestionType, EHRSimulationMode, ReconciliationStatus
from app.services.hospital_service import HospitalService
from app.services.doctor_service import DoctorService
from app.services.scheduling_service import SchedulingService
from app.services.appointment_service import AppointmentService
from app.services.questionnaire_service import QuestionnaireService
from app.ai.agent import ai_agent
from app.integrations.mock_ehr import mock_ehr_connector
from app.schemas.doctor import AvailabilityCreate
from app.schemas.appointment import AppointmentCreate
from app.schemas.questionnaire import QuestionnaireAnswerSubmit


@pytest.mark.asyncio
async def test_complete_e2e_acceptance_workflow(db_session: AsyncSession):
    """
    Executes the complete Acceptance Test scenario (PRD Section 45):
    Steps 1-23: Happy Path Booking & Intake
    Steps 24-29: Failure & Timeout Recovery
    """
    # STEP 1 & 2: Create & Approve Hospital A
    hosp = Hospital(
        name="Acceptance Memorial Hospital",
        slug="acceptance-memorial",
        address="500 Health Blvd",
        phone="555-0100",
        email="info@acceptance.org",
        status=HospitalStatus.DRAFT,
    )
    db_session.add(hosp)
    await db_session.flush()

    admin_user = User(email="super.admin@platform.local", hashed_password="pw", full_name="Super Admin", role=UserRole.PLATFORM_ADMIN)
    db_session.add(admin_user)
    await db_session.flush()

    await HospitalService.approve_hospital(db_session, hosp.id, admin_user.id)
    assert hosp.status == HospitalStatus.APPROVED

    # STEP 3 & 4: Hospital Admin creates Doctor A with Calendar and Availability
    spec = Specialty(hospital_id=hosp.id, name="Orthopedics", code="ORTHO")
    db_session.add(spec)
    await db_session.flush()

    doc = Doctor(
        name="Dr. Acceptance Rao",
        hospital_id=hosp.id,
        specialty_id=spec.id,
        qualifications="MD, FAAOS",
        experience_years=10,
        appointment_duration_minutes=30,
        status=DoctorStatus.ACTIVE,
    )
    db_session.add(doc)
    await db_session.flush()

    cal = Calendar(doctor_id=doc.id, hospital_id=hosp.id, is_active=True)
    db_session.add(cal)
    await db_session.flush()

    # Configure Monday to Friday 09:00 - 17:00
    for d in range(5):
        db_session.add(Availability(
            calendar_id=cal.id,
            hospital_id=hosp.id,
            day_of_week=d,
            start_time="09:00",
            end_time="17:00",
            slot_duration_minutes=30,
            is_active=True,
        ))
    await db_session.flush()

    # Pre-visit questionnaire configuration
    q_intake = Questionnaire(
        hospital_id=hosp.id,
        specialty_id=spec.id,
        doctor_id=doc.id,
        title="Orthopedic Intake Form",
        is_active=True,
    )
    db_session.add(q_intake)
    await db_session.flush()
    db_session.add(QuestionnaireQuestion(
        questionnaire_id=q_intake.id,
        prompt="Which joint or bone is hurting?",
        question_type=QuestionType.SHORT_TEXT,
    ))
    await db_session.flush()

    # STEP 5: Create patient
    pat_user = User(email="pat.acceptance@test.com", hashed_password="pw", full_name="John Patient", role=UserRole.PATIENT)
    db_session.add(pat_user)
    await db_session.flush()
    patient = Patient(user_id=pat_user.id, first_name="John", last_name="Patient", email="pat.acceptance@test.com", phone="555-7777")
    db_session.add(patient)
    await db_session.flush()

    # STEP 6 & 7: Patient interacts with AI Assistant: "I need an orthopedic doctor sometime this week."
    chat_step1 = await ai_agent.chat(
        db=db_session,
        user_id=pat_user.id,
        patient_id=patient.id,
        hospital_id=hosp.id,
        message_text="I need an orthopedic doctor sometime this week.",
    )

    # STEP 8-11: AI identifies intent, queries real availability, presents real slots
    assert "Dr. Acceptance Rao" in chat_step1.message
    assert "Option 1" in chat_step1.message or "available" in chat_step1.message.lower()

    # STEP 12: Patient selects slot
    chat_step2 = await ai_agent.chat(
        db=db_session,
        user_id=pat_user.id,
        patient_id=patient.id,
        hospital_id=hosp.id,
        conversation_id=chat_step1.conversation_id,
        message_text="I'll take the first option please.",
    )

    # STEP 13-18: Availability revalidated -> PENDING -> EHR verified -> CONFIRMED
    assert "CONFIRMED" in chat_step2.context_state.get("appointment_status", "") or "confirmed" in chat_step2.message.lower()
    created_appt_id = chat_step2.context_state.get("appointment_status")

    # Verify internal DB appointment
    appts = await AppointmentService.list_appointments(db_session, doctor_id=doc.id)
    assert len(appts) == 1
    appt = appts[0]
    assert appt.status == AppointmentStatus.CONFIRMED
    assert appt.external_appointment_id is not None

    # STEP 19 & 20: Pre-visit Questionnaire assigned and answered conversationally
    chat_step3 = await ai_agent.chat(
        db=db_session,
        user_id=pat_user.id,
        patient_id=patient.id,
        hospital_id=hosp.id,
        conversation_id=chat_step1.conversation_id,
        message_text="My left shoulder hurts when lifting things. No previous surgeries.",
    )
    assert "questionnaire" in chat_step3.message.lower() or "recorded" in chat_step3.message.lower()

    # STEP 21: Doctor can view authorized questionnaire responses
    q_resp = await db_session.execute(select(QuestionnaireResponse).where(QuestionnaireResponse.appointment_id == appt.id))
    resp_record = q_resp.scalar_one_or_none()
    assert resp_record is not None
    assert resp_record.is_completed is True

    # Doctor review
    await QuestionnaireService.doctor_review_response(
        db_session, response_id=resp_record.id, doctor_id=doc.id, notes="Patient has acute rotator cuff strain suspected."
    )
    assert resp_record.reviewed_by_doctor_id == doc.id

    # ----------------------------------------------------
    # STEP 24-29: FAILURE SCENARIO
    # ----------------------------------------------------
    # Force Mock EHR timeout with UNKNOWN_OUTCOME
    mock_ehr_connector.set_simulation_mode(
        mode=EHRSimulationMode.UNKNOWN_OUTCOME,
        target_operation="CREATE_APPOINTMENT",
        countdown=1,
    )

    # Book next available slot
    slots = await SchedulingService.get_available_slots(
        db_session, doctor_id=doc.id,
        start_date=datetime.datetime.now(datetime.timezone.utc).date() + datetime.timedelta(days=1),
        end_date=datetime.datetime.now(datetime.timezone.utc).date() + datetime.timedelta(days=2),
    )
    assert len(slots) > 0
    fail_slot = slots[0]

    # Booking attempt:
    fail_result = await AppointmentService.book_appointment(
        db=db_session,
        appt_in=AppointmentCreate(
            doctor_id=doc.id,
            hospital_id=hosp.id,
            start_time=fail_slot.start_time,
            reason_for_visit="Followup check",
        ),
        patient_id=patient.id,
    )

    # STEP 25: System identifies unknown outcome and triggers recovery
    assert fail_result["timeout_encountered"] is True
    # STEP 26 & 27: Verification discovers appointment exists, synchronizes without duplicate
    assert fail_result["status"] == AppointmentStatus.CONFIRMED.value
    assert fail_result["recovery"]["recovered"] is True

    # STEP 28: Prevent duplicate booking
    with pytest.raises(Exception):
        await AppointmentService.book_appointment(
            db=db_session,
            appt_in=AppointmentCreate(
                doctor_id=doc.id,
                hospital_id=hosp.id,
                start_time=fail_slot.start_time,
                reason_for_visit="Duplicate attempt",
            ),
            patient_id=patient.id,
        )

    # STEP 29: Reconciliation and audit records exist
    recs = await db_session.execute(select(ReconciliationRecord).where(ReconciliationRecord.hospital_id == hosp.id))
    all_recs = recs.scalars().all()
    assert len(all_recs) >= 1
    assert any(r.status == ReconciliationStatus.RESOLVED for r in all_recs)
