import asyncio
import datetime
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import AsyncSessionLocal, init_db
from app.core.security import get_password_hash
from app.db.models.auth import User, HospitalStaff
from app.db.models.hospital import Hospital, Department, Specialty
from app.db.models.doctor import Doctor, Calendar, Availability, BlockedSlot
from app.db.models.patient import Patient, UserPreference
from app.db.models.appointment import Appointment, AppointmentHistory
from app.db.models.questionnaire import Questionnaire, QuestionnaireQuestion
from app.db.models.enums import UserRole, HospitalStatus, DoctorStatus, AppointmentStatus, QuestionType, ConsultationType
from app.integrations.mock_ehr import mock_ehr_connector


DEMO_PASSWORD = "Password123!"


async def seed_database():
    print("Initializing tables...")
    await init_db()

    async with AsyncSessionLocal() as session:
        # Check if already seeded
        existing_user = await session.execute(select(User).where(User.email == "platform.admin@healthcare.local"))
        if existing_user.scalar_one_or_none():
            print("Database already seeded. Skipping.")
            return

        print("Seeding Platform Admin...")
        platform_admin = User(
            email="platform.admin@healthcare.local",
            hashed_password=get_password_hash(DEMO_PASSWORD),
            full_name="Platform Administrator",
            role=UserRole.PLATFORM_ADMIN,
            is_active=True,
        )
        session.add(platform_admin)

        # ----------------------------------------------------
        # HOSPITAL 1: Metro General Hospital (Approved)
        # ----------------------------------------------------
        print("Seeding Hospital 1: Metro General Hospital...")
        hosp1 = Hospital(
            name="Metro General Hospital",
            slug="metro-general",
            address="100 Medical Center Way, Metro City, NY 10001",
            phone="+1-555-0100",
            email="contact@metrogeneral.org",
            website="https://metrogeneral.org",
            status=HospitalStatus.APPROVED,
            configuration={"timezone": "America/New_York", "voice_intake_enabled": True},
        )
        session.add(hosp1)
        await session.flush()

        # Admin for Hosp 1
        hosp1_admin_user = User(
            email="admin@metrogeneral.org",
            hashed_password=get_password_hash(DEMO_PASSWORD),
            full_name="Metro Admin",
            role=UserRole.HOSPITAL_ADMIN,
            is_active=True,
        )
        session.add(hosp1_admin_user)
        await session.flush()

        hosp1_staff = HospitalStaff(
            user_id=hosp1_admin_user.id,
            hospital_id=hosp1.id,
            role_title="Chief Medical Operations Admin",
        )
        session.add(hosp1_staff)

        # Specialties & Departments for Hosp 1
        spec_ortho = Specialty(hospital_id=hosp1.id, name="Orthopedics", code="ORTHO", description="Bone and joint surgery")
        spec_cardio = Specialty(hospital_id=hosp1.id, name="Cardiology", code="CARDIO", description="Heart health and cardiovascular care")
        dept_surgery = Department(hospital_id=hosp1.id, name="Surgical Services", code="SURG")
        dept_cardio = Department(hospital_id=hosp1.id, name="Cardiovascular Care", code="CARD")
        session.add_all([spec_ortho, spec_cardio, dept_surgery, dept_cardio])
        await session.flush()

        # Doctor 1: Dr. Marcus Rao (Orthopedics)
        doc1_user = User(
            email="dr.rao@metrogeneral.org",
            hashed_password=get_password_hash(DEMO_PASSWORD),
            full_name="Dr. Marcus Rao",
            role=UserRole.DOCTOR,
            is_active=True,
        )
        session.add(doc1_user)
        await session.flush()

        doc1 = Doctor(
            name="Dr. Marcus Rao",
            hospital_id=hosp1.id,
            specialty_id=spec_ortho.id,
            department_id=dept_surgery.id,
            qualifications="MD, FAAOS (Orthopedic Surgery)",
            experience_years=14,
            languages=["English", "Spanish"],
            consultation_types=["IN_PERSON", "VIDEO"],
            appointment_duration_minutes=30,
            status=DoctorStatus.ACTIVE,
            user_id=doc1_user.id,
            external_provider_id="EHR-DOC-RAO",
            bio="Specialist in orthopedic joint reconstruction and sports injury management.",
        )
        session.add(doc1)
        await session.flush()

        # Doctor 1 Calendar & Mon-Fri 09:00 - 17:00 Availability
        cal1 = Calendar(doctor_id=doc1.id, hospital_id=hosp1.id, timezone="UTC", is_active=True)
        session.add(cal1)
        await session.flush()

        for day in range(5):  # Mon-Fri
            session.add(Availability(
                calendar_id=cal1.id,
                hospital_id=hosp1.id,
                day_of_week=day,
                start_time="09:00",
                end_time="17:00",
                slot_duration_minutes=30,
                is_active=True,
            ))

        # Doctor 2: Dr. Sarah Chen (Cardiology)
        doc2_user = User(
            email="dr.chen@metrogeneral.org",
            hashed_password=get_password_hash(DEMO_PASSWORD),
            full_name="Dr. Sarah Chen",
            role=UserRole.DOCTOR,
            is_active=True,
        )
        session.add(doc2_user)
        await session.flush()

        doc2 = Doctor(
            name="Dr. Sarah Chen",
            hospital_id=hosp1.id,
            specialty_id=spec_cardio.id,
            department_id=dept_cardio.id,
            qualifications="MD, FACC (Cardiology)",
            experience_years=11,
            languages=["English", "Mandarin"],
            consultation_types=["IN_PERSON", "VIDEO"],
            appointment_duration_minutes=30,
            status=DoctorStatus.ACTIVE,
            user_id=doc2_user.id,
            external_provider_id="EHR-DOC-CHEN",
            bio="Preventive cardiology and cardiac rhythm disorders specialist.",
        )
        session.add(doc2)
        await session.flush()

        cal2 = Calendar(doctor_id=doc2.id, hospital_id=hosp1.id, timezone="UTC", is_active=True)
        session.add(cal2)
        await session.flush()

        for day in range(5):
            session.add(Availability(
                calendar_id=cal2.id,
                hospital_id=hosp1.id,
                day_of_week=day,
                start_time="09:00",
                end_time="17:00",
                slot_duration_minutes=30,
                is_active=True,
            ))

        # Pre-visit Questionnaire for Hosp 1 Orthopedics
        q_ortho = Questionnaire(
            hospital_id=hosp1.id,
            specialty_id=spec_ortho.id,
            doctor_id=doc1.id,
            title="Orthopedic Intake & Joint Health Questionnaire",
            description="Approved pre-visit intake questions for orthopedic consultation.",
            is_active=True,
        )
        session.add(q_ortho)
        await session.flush()

        session.add_all([
            QuestionnaireQuestion(
                questionnaire_id=q_ortho.id,
                prompt="Which joint or body area is experiencing pain (e.g. shoulder, knee, back)?",
                question_type=QuestionType.SHORT_TEXT,
                order_index=1,
            ),
            QuestionnaireQuestion(
                questionnaire_id=q_ortho.id,
                prompt="On a scale of 1-10, how severe is your current pain?",
                question_type=QuestionType.NUMERIC,
                order_index=2,
            ),
            QuestionnaireQuestion(
                questionnaire_id=q_ortho.id,
                prompt="Did this injury occur from a specific fall, athletic activity, or trauma?",
                question_type=QuestionType.YES_NO,
                order_index=3,
            ),
            QuestionnaireQuestion(
                questionnaire_id=q_ortho.id,
                prompt="Have you previously had surgery, physical therapy, or injections for this joint?",
                question_type=QuestionType.SHORT_TEXT,
                order_index=4,
            ),
        ])

        # ----------------------------------------------------
        # HOSPITAL 2: Apex Healthcare Pavilion (Approved)
        # ----------------------------------------------------
        print("Seeding Hospital 2: Apex Healthcare Pavilion...")
        hosp2 = Hospital(
            name="Apex Healthcare Pavilion",
            slug="apex-healthcare",
            address="742 Evergreen Blvd, San Francisco, CA 94107",
            phone="+1-555-0200",
            email="info@apexhealthcare.com",
            website="https://apexhealthcare.com",
            status=HospitalStatus.APPROVED,
            configuration={"timezone": "America/Los_Angeles"},
        )
        session.add(hosp2)
        await session.flush()

        hosp2_admin_user = User(
            email="admin@apexhealthcare.com",
            hashed_password=get_password_hash(DEMO_PASSWORD),
            full_name="Apex Admin",
            role=UserRole.HOSPITAL_ADMIN,
            is_active=True,
        )
        session.add(hosp2_admin_user)
        await session.flush()

        hosp2_staff = HospitalStaff(
            user_id=hosp2_admin_user.id,
            hospital_id=hosp2.id,
            role_title="Clinical Operations Director",
        )
        session.add(hosp2_staff)

        spec_derm = Specialty(hospital_id=hosp2.id, name="Dermatology", code="DERM", description="Skin health and dermatology")
        spec_genmed = Specialty(hospital_id=hosp2.id, name="General Medicine", code="GENMED", description="Primary and general care")
        dept_derm = Department(hospital_id=hosp2.id, name="Dermatological Clinic", code="DERMC")
        dept_primary = Department(hospital_id=hosp2.id, name="Primary Care Unit", code="PCU")
        session.add_all([spec_derm, spec_genmed, dept_derm, dept_primary])
        await session.flush()

        # Doctor 3: Dr. Priya Patel (Dermatology)
        doc3_user = User(
            email="dr.patel@apexhealthcare.com",
            hashed_password=get_password_hash(DEMO_PASSWORD),
            full_name="Dr. Priya Patel",
            role=UserRole.DOCTOR,
            is_active=True,
        )
        session.add(doc3_user)
        await session.flush()

        doc3 = Doctor(
            name="Dr. Priya Patel",
            hospital_id=hosp2.id,
            specialty_id=spec_derm.id,
            department_id=dept_derm.id,
            qualifications="MD, FAAD",
            experience_years=8,
            languages=["English", "Hindi"],
            consultation_types=["IN_PERSON", "VIDEO"],
            appointment_duration_minutes=30,
            status=DoctorStatus.ACTIVE,
            user_id=doc3_user.id,
            external_provider_id="EHR-DOC-PATEL",
            bio="General and cosmetic dermatology specialist.",
        )
        session.add(doc3)
        await session.flush()

        cal3 = Calendar(doctor_id=doc3.id, hospital_id=hosp2.id, timezone="UTC", is_active=True)
        session.add(cal3)
        await session.flush()

        for day in range(5):
            session.add(Availability(
                calendar_id=cal3.id,
                hospital_id=hosp2.id,
                day_of_week=day,
                start_time="10:00",
                end_time="16:00",
                slot_duration_minutes=30,
                is_active=True,
            ))

        # Doctor 4: Dr. James Wilson (General Medicine)
        doc4_user = User(
            email="dr.wilson@apexhealthcare.com",
            hashed_password=get_password_hash(DEMO_PASSWORD),
            full_name="Dr. James Wilson",
            role=UserRole.DOCTOR,
            is_active=True,
        )
        session.add(doc4_user)
        await session.flush()

        doc4 = Doctor(
            name="Dr. James Wilson",
            hospital_id=hosp2.id,
            specialty_id=spec_genmed.id,
            department_id=dept_primary.id,
            qualifications="MD, ABFM",
            experience_years=16,
            languages=["English"],
            consultation_types=["IN_PERSON", "PHONE"],
            appointment_duration_minutes=30,
            status=DoctorStatus.ACTIVE,
            user_id=doc4_user.id,
            external_provider_id="EHR-DOC-WILSON",
            bio="Comprehensive family and general internal medicine.",
        )
        session.add(doc4)
        await session.flush()

        cal4 = Calendar(doctor_id=doc4.id, hospital_id=hosp2.id, timezone="UTC", is_active=True)
        session.add(cal4)
        await session.flush()

        for day in range(5):
            session.add(Availability(
                calendar_id=cal4.id,
                hospital_id=hosp2.id,
                day_of_week=day,
                start_time="09:00",
                end_time="17:00",
                slot_duration_minutes=30,
                is_active=True,
            ))

        # ----------------------------------------------------
        # PATIENT SEED: Jane Doe
        # ----------------------------------------------------
        print("Seeding Patient: Jane Doe...")
        patient_user = User(
            email="jane.doe@example.com",
            hashed_password=get_password_hash(DEMO_PASSWORD),
            full_name="Jane Doe",
            role=UserRole.PATIENT,
            phone="+1-555-0999",
            is_active=True,
        )
        session.add(patient_user)
        await session.flush()

        patient = Patient(
            user_id=patient_user.id,
            first_name="Jane",
            last_name="Doe",
            phone="+1-555-0999",
            email="jane.doe@example.com",
            date_of_birth=datetime.date(1988, 4, 12),
            gender="Female",
            address="452 Elm Street, Springfield, IL 62701",
            insurance_info={"provider": "BlueCross Shield", "policy_number": "BCS-992182"},
            emergency_contact={"name": "John Doe", "relation": "Spouse", "phone": "+1-555-0998"},
            external_patient_id="EHR-PAT-001",
            primary_hospital_id=hosp1.id,
        )
        session.add(patient)
        await session.flush()

        pref = UserPreference(
            user_id=patient_user.id,
            preferred_hospital_id=hosp1.id,
            preferred_communication_channel="IN_APP",
            language="en",
            notification_opt_in=True,
        )
        session.add(pref)

        # Blocked slot for Dr. Rao (Thursday afternoon conference)
        thursday_start = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=2)
        thursday_start = thursday_start.replace(hour=14, minute=0, second=0, microsecond=0)
        thursday_end = thursday_start.replace(hour=16, minute=0, second=0, microsecond=0)

        session.add(BlockedSlot(
            doctor_id=doc1.id,
            hospital_id=hosp1.id,
            start_time=thursday_start,
            end_time=thursday_end,
            reason="Orthopedic Grand Rounds Conference",
        ))

        await session.commit()
        print("\n=======================================================")
        print("HEALTHCARE ACCESS PLATFORM SEEDING COMPLETED")
        print("=======================================================")
        print("DEMO CREDENTIALS (All accounts use password: Password123!)")
        print("-------------------------------------------------------")
        print("1. Platform Admin:")
        print("   Email: platform.admin@healthcare.local")
        print("\n2. Hospital 1 Admin (Metro General Hospital):")
        print("   Email: admin@metrogeneral.org")
        print("\n3. Doctor (Dr. Marcus Rao - Orthopedics):")
        print("   Email: dr.rao@metrogeneral.org")
        print("\n4. Patient (Jane Doe):")
        print("   Email: jane.doe@example.com")
        print("=======================================================\n")


if __name__ == "__main__":
    asyncio.run(seed_database())
