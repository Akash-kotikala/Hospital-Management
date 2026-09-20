import datetime
from typing import List, Optional, Dict, Any
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import EntityNotFoundException, AppException
from app.db.models.questionnaire import Questionnaire, QuestionnaireQuestion, QuestionnaireResponse
from app.db.models.appointment import Appointment
from app.schemas.questionnaire import QuestionnaireCreate, QuestionCreate, QuestionnaireAnswerSubmit
from app.services.audit_service import AuditService


class QuestionnaireService:
    @staticmethod
    async def create_questionnaire(db: AsyncSession, q_in: QuestionnaireCreate) -> Questionnaire:
        questionnaire = Questionnaire(
            hospital_id=q_in.hospital_id,
            title=q_in.title,
            description=q_in.description,
            specialty_id=q_in.specialty_id,
            doctor_id=q_in.doctor_id,
            is_active=True,
        )
        db.add(questionnaire)
        await db.flush()

        for idx, q in enumerate(q_in.questions):
            question = QuestionnaireQuestion(
                questionnaire_id=questionnaire.id,
                prompt=q.prompt,
                question_type=q.question_type,
                options=q.options,
                is_required=q.is_required,
                order_index=q.order_index or idx,
                validation_rules=q.validation_rules,
            )
            db.add(question)

        await db.flush()
        return questionnaire

    @staticmethod
    async def get_questionnaire(db: AsyncSession, questionnaire_id: str) -> Questionnaire:
        result = await db.execute(
            select(Questionnaire)
            .options(selectinload(Questionnaire.questions))
            .where(Questionnaire.id == questionnaire_id)
        )
        q = result.scalar_one_or_none()
        if not q:
            raise EntityNotFoundException("Questionnaire", questionnaire_id)
        return q

    @staticmethod
    async def list_questionnaires(
        db: AsyncSession,
        hospital_id: Optional[str] = None,
        specialty_id: Optional[str] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> List[Questionnaire]:
        query = select(Questionnaire).options(selectinload(Questionnaire.questions)).offset(skip).limit(limit)
        if hospital_id:
            query = query.where(Questionnaire.hospital_id == hospital_id)
        if specialty_id:
            query = query.where(Questionnaire.specialty_id == specialty_id)
        result = await db.execute(query)
        return list(result.scalars().all())

    @staticmethod
    async def find_questionnaire_for_appointment(db: AsyncSession, appointment_id: str) -> Optional[Questionnaire]:
        """Finds most specific active questionnaire (doctor-specific -> specialty -> hospital default)."""
        appt = await db.get(Appointment, appointment_id)
        if not appt:
            return None

        # 1. Doctor-specific
        q_doc = await db.execute(
            select(Questionnaire)
            .options(selectinload(Questionnaire.questions))
            .where(Questionnaire.doctor_id == appt.doctor_id, Questionnaire.is_active == True)
        )
        found = q_doc.scalars().first()
        if found:
            return found

        # 2. Specialty or Hospital-wide
        q_gen = await db.execute(
            select(Questionnaire)
            .options(selectinload(Questionnaire.questions))
            .where(Questionnaire.hospital_id == appt.hospital_id, Questionnaire.is_active == True)
        )
        return q_gen.scalars().first()

    @staticmethod
    async def submit_response(
        db: AsyncSession,
        submission: QuestionnaireAnswerSubmit,
        patient_id: str,
    ) -> QuestionnaireResponse:
        appt = await db.get(Appointment, submission.appointment_id)
        if not appt:
            raise EntityNotFoundException("Appointment", submission.appointment_id)

        questionnaire = await QuestionnaireService.find_questionnaire_for_appointment(db, appt.id)
        if not questionnaire:
            raise AppException("NO_ACTIVE_QUESTIONNAIRE", "No active questionnaire configured for this appointment.")

        # Check existing response
        existing = await db.execute(
            select(QuestionnaireResponse).where(
                QuestionnaireResponse.appointment_id == appt.id,
                QuestionnaireResponse.patient_id == patient_id,
            )
        )
        resp = existing.scalar_one_or_none()
        if not resp:
            resp = QuestionnaireResponse(
                questionnaire_id=questionnaire.id,
                appointment_id=appt.id,
                patient_id=patient_id,
                hospital_id=appt.hospital_id,
                answers=submission.answers,
                is_completed=submission.is_completed,
                completed_at=datetime.datetime.now(datetime.timezone.utc) if submission.is_completed else None,
            )
            db.add(resp)
        else:
            resp.answers.update(submission.answers)
            resp.is_completed = submission.is_completed
            if submission.is_completed:
                resp.completed_at = datetime.datetime.now(datetime.timezone.utc)

        await db.flush()

        await AuditService.log_audit_event(
            db=db,
            action="QUESTIONNAIRE_SUBMITTED",
            resource_type="QUESTIONNAIRE_RESPONSE",
            resource_id=resp.id,
            hospital_id=appt.hospital_id,
            user_id=patient_id,
            details={"appointment_id": appt.id, "is_completed": resp.is_completed}
        )
        return resp

    @staticmethod
    async def doctor_review_response(
        db: AsyncSession,
        response_id: str,
        doctor_id: str,
        notes: str,
    ) -> QuestionnaireResponse:
        resp = await db.get(QuestionnaireResponse, response_id)
        if not resp:
            raise EntityNotFoundException("QuestionnaireResponse", response_id)

        resp.reviewed_by_doctor_id = doctor_id
        resp.reviewed_at = datetime.datetime.now(datetime.timezone.utc)
        resp.doctor_notes = notes
        await db.flush()

        await AuditService.log_audit_event(
            db=db,
            action="QUESTIONNAIRE_REVIEWED_BY_DOCTOR",
            resource_type="QUESTIONNAIRE_RESPONSE",
            resource_id=resp.id,
            hospital_id=resp.hospital_id,
            details={"doctor_id": doctor_id}
        )
        return resp
