from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.db.models.auth import User
from app.db.models.enums import UserRole
from app.db.models.platform import AuditEvent, OperationalEvent
from app.api.deps import require_role
from app.schemas.audit import AuditEventResponse, OperationalEventResponse
from app.schemas.common import ApiResponse

router = APIRouter(prefix="/audit", tags=["Audit & Observability"])


@router.get("", response_model=ApiResponse[List[AuditEventResponse]])
async def list_audit_events(
    hospital_id: Optional[str] = None,
    correlation_id: Optional[str] = None,
    action: Optional[str] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.PLATFORM_ADMIN, UserRole.HOSPITAL_ADMIN)),
):
    """Query audit trail with correlation IDs, actions, and timestamps."""
    query = select(AuditEvent).offset(skip).limit(limit).order_by(AuditEvent.created_at.desc())
    if current_user.role == UserRole.HOSPITAL_ADMIN and current_user.staff_profile:
        query = query.where(AuditEvent.hospital_id == current_user.staff_profile.hospital_id)
    elif hospital_id:
        query = query.where(AuditEvent.hospital_id == hospital_id)

    if correlation_id:
        query = query.where(AuditEvent.correlation_id == correlation_id)
    if action:
        query = query.where(AuditEvent.action == action)

    res = await db.execute(query)
    return ApiResponse(success=True, data=list(res.scalars().all()))


@router.get("/operational", response_model=ApiResponse[List[OperationalEventResponse]])
async def list_operational_events(
    severity: Optional[str] = None,
    service_name: Optional[str] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.PLATFORM_ADMIN)),
):
    """Platform administrator view of operational errors and background events."""
    query = select(OperationalEvent).offset(skip).limit(limit).order_by(OperationalEvent.created_at.desc())
    if severity:
        query = query.where(OperationalEvent.severity == severity)
    if service_name:
        query = query.where(OperationalEvent.service_name == service_name)

    res = await db.execute(query)
    return ApiResponse(success=True, data=list(res.scalars().all()))
