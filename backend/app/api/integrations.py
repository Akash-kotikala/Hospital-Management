from typing import List, Optional
from fastapi import APIRouter, Depends, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db.database import get_db
from app.db.models.auth import User
from app.db.models.enums import UserRole, ReconciliationStatus, EHRSimulationMode
from app.api.deps import get_current_user, require_role, verify_tenant_access
from app.services.reconciliation_service import ReconciliationService
from app.integrations.mock_ehr import mock_ehr_connector
from app.db.models.integration import IntegrationOperation, ReconciliationRecord
from app.schemas.integration import (
    FailureModeRequest,
    FailureModeStatusResponse,
    ReconciliationRecordResponse,
    ReconciliationResolveRequest,
    IntegrationOperationResponse,
)
from app.schemas.common import ApiResponse

router = APIRouter(prefix="/integrations", tags=["EHR Integration & Reconciliation"])


@router.get("/status", response_model=ApiResponse[dict])
async def get_integration_status():
    """Returns the live status of the EHR connector and active simulation modes."""
    return ApiResponse(
        success=True,
        data={
            "connector": "MockEHRConnector",
            "active": True,
            "simulation": mock_ehr_connector.get_simulation_status(),
        }
    )


@router.post("/failure-mode", response_model=ApiResponse[FailureModeStatusResponse])
async def set_failure_mode(
    req: FailureModeRequest,
    current_user: User = Depends(require_role(UserRole.PLATFORM_ADMIN, UserRole.HOSPITAL_ADMIN)),
):
    """
    Demo Control: Intentionally triggers EHR failures (e.g. TIMEOUT, UNKNOWN_OUTCOME)
    to demonstrate the failure recovery state machine.
    """
    mock_ehr_connector.set_simulation_mode(
        mode=req.mode,
        target_operation=req.target_operation or "CREATE_APPOINTMENT",
        countdown=req.active_until_resets,
    )
    status_info = mock_ehr_connector.get_simulation_status()
    return ApiResponse(
        success=True,
        data=FailureModeStatusResponse(
            current_mode=EHRSimulationMode(status_info["current_mode"]),
            active_until_resets=status_info["active_until_resets"],
            message=f"Mock EHR will trigger '{req.mode.value}' on the next {req.active_until_resets} '{req.target_operation}' operation(s).",
        ),
    )


@router.get("/operations", response_model=ApiResponse[List[IntegrationOperationResponse]])
async def list_integration_operations(
    hospital_id: Optional[str] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.PLATFORM_ADMIN, UserRole.HOSPITAL_ADMIN)),
):
    """Audit log of all outbound EHR connector requests, responses, and latencies."""
    query = select(IntegrationOperation).offset(skip).limit(limit).order_by(IntegrationOperation.created_at.desc())
    if current_user.role == UserRole.HOSPITAL_ADMIN and current_user.staff_profile:
        query = query.where(IntegrationOperation.hospital_id == current_user.staff_profile.hospital_id)
    elif hospital_id:
        query = query.where(IntegrationOperation.hospital_id == hospital_id)

    res = await db.execute(query)
    return ApiResponse(success=True, data=list(res.scalars().all()))


@router.get("/reconciliation", response_model=ApiResponse[List[ReconciliationRecordResponse]])
async def list_reconciliation_records(
    hospital_id: Optional[str] = None,
    status: Optional[ReconciliationStatus] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.PLATFORM_ADMIN, UserRole.HOSPITAL_ADMIN)),
):
    """View unresolved and investigated reconciliation records resulting from timeouts or sync failures."""
    scoped_hospital = hospital_id
    if current_user.role == UserRole.HOSPITAL_ADMIN and current_user.staff_profile:
        scoped_hospital = current_user.staff_profile.hospital_id

    records = await ReconciliationService.list_records(
        db=db, hospital_id=scoped_hospital, status=status, skip=skip, limit=limit
    )
    return ApiResponse(success=True, data=records)


@router.post("/reconciliation/{id}/resolve", response_model=ApiResponse[ReconciliationRecordResponse])
async def resolve_reconciliation_record(
    id: str,
    req: ReconciliationResolveRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.PLATFORM_ADMIN, UserRole.HOSPITAL_ADMIN)),
):
    """Administrator manually resolves a reconciliation investigation record."""
    resolved = await ReconciliationService.resolve_record(db, record_id=id, resolution=req.resolution, mark_as=req.mark_as)
    return ApiResponse(success=True, data=resolved)
