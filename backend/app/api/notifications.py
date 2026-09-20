from typing import List, Optional
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.database import get_db
from app.db.models.auth import User
from app.api.deps import get_current_user
from app.services.notification_service import NotificationService
from app.schemas.workflow import NotificationResponse
from app.schemas.common import ApiResponse

router = APIRouter(prefix="/notifications", tags=["Notifications"])


@router.get("", response_model=ApiResponse[List[NotificationResponse]])
async def get_my_notifications(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retrieve notifications dispatched to current user/patient."""
    patient_id = current_user.patient_profile.id if current_user.patient_profile else None
    notifs = await NotificationService.list_notifications(
        db,
        user_id=current_user.id,
        patient_id=patient_id,
        limit=25,
    )
    return ApiResponse(success=True, data=notifs)
