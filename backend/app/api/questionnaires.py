from typing import List, Optional
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.db.database import get_db
from app.db.models.auth import User
from app.db.models.enums import UserRole
from app.api.deps import get_current_user, require_role, verify_tenant_access
from app.services.questionnaire_service import QuestionnaireService
from app.schemas.questionnaire import (
    QuestionnaireCreate,
    QuestionnaireResponseModel,
    QuestionnaireAnswerSubmit,
    QuestionnaireSubmissionResponse,
    DoctorReviewSubmit,
)
from app.schemas.common import ApiResponse
from app.db.models.questionnaire import QuestionnaireResponse

router = APIRouter(prefix="/questionnaires", tags=["Pre-Visit Questionnaires"])


@router.post("", response_model=ApiResponse[QuestionnaireResponseModel], status_code=status.HTTP_201_CREATED)
async def create_questionnaire(
    q_in: QuestionnaireCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.PLATFORM_ADMIN, UserRole.HOSPITAL_ADMIN)),
):
    """Configure an approved pre-visit health questionnaire."""
    await verify_tenant_access(q_in.hospital_id, current_user)
    q = await QuestionnaireService.create_questionnaire(db, q_in)
    full_q = await QuestionnaireService.get_questionnaire(db, q.id)
    return ApiResponse(success=True, data=full_q)


@router.get("", response_model=ApiResponse[List[QuestionnaireResponseModel]])
async def list_questionnaires(
    hospital_id: Optional[str] = None,
    specialty_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """List questionnaires configured for a hospital or specialty."""
    qs = await QuestionnaireService.list_questionnaires(db, hospital_id=hospital_id, specialty_id=specialty_id)
    return ApiResponse(success=True, data=qs)


@router.get("/{id}", response_model=ApiResponse[QuestionnaireResponseModel])
async def get_questionnaire(id: str, db: AsyncSession = Depends(get_db)):
    """Retrieve questionnaire with approved questions."""
    q = await QuestionnaireService.get_questionnaire(db, id)
    return ApiResponse(success=True, data=q)


@router.post("/{id}/responses", response_model=ApiResponse[QuestionnaireSubmissionResponse], status_code=status.HTTP_201_CREATED)
async def submit_questionnaire_response(
    id: str,
    submission: QuestionnaireAnswerSubmit,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Submit patient responses to an assigned pre-visit questionnaire."""
    patient_id = current_user.patient_profile.id if current_user.patient_profile else current_user.id
    resp = await QuestionnaireService.submit_response(db, submission, patient_id=patient_id)
    return ApiResponse(success=True, data=resp)


@router.get("/responses/by-appointment/{appointment_id}", response_model=ApiResponse[Optional[QuestionnaireSubmissionResponse]])
async def get_appointment_questionnaire_response(
    appointment_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retrieve questionnaire answers submitted for an appointment."""
    query = select(QuestionnaireResponse).where(QuestionnaireResponse.appointment_id == appointment_id)
    result = await db.execute(query)
    resp = result.scalar_one_or_none()
    return ApiResponse(success=True, data=resp)


@router.post("/responses/{response_id}/review", response_model=ApiResponse[QuestionnaireSubmissionResponse])
async def doctor_review_questionnaire(
    response_id: str,
    review_in: DoctorReviewSubmit,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.DOCTOR, UserRole.HOSPITAL_ADMIN)),
):
    """Doctor reviews patient questionnaire responses and adds clinical notes."""
    doctor_id = current_user.doctor_profile.id if current_user.doctor_profile else current_user.id
    reviewed = await QuestionnaireService.doctor_review_response(
        db, response_id=response_id, doctor_id=doctor_id, notes=review_in.doctor_notes
    )
    return ApiResponse(success=True, data=reviewed)
