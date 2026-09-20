from typing import List, Optional
from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.db.models.auth import User
from app.db.models.enums import UserRole
from app.api.deps import get_current_user, require_role, verify_tenant_access
from app.services.workflow_service import WorkflowService
from app.db.models.workflow import Workflow, WorkflowExecution
from app.schemas.workflow import WorkflowCreate, WorkflowResponse, WorkflowExecutionResponse
from app.schemas.common import ApiResponse
from app.core.exceptions import EntityNotFoundException

router = APIRouter(prefix="/workflows", tags=["Workflows"])


@router.post("", response_model=ApiResponse[WorkflowResponse], status_code=status.HTTP_201_CREATED)
async def create_workflow(
    wf_in: WorkflowCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.PLATFORM_ADMIN, UserRole.HOSPITAL_ADMIN)),
):
    await verify_tenant_access(wf_in.hospital_id, current_user)
    wf = Workflow(
        hospital_id=wf_in.hospital_id,
        name=wf_in.name,
        event_trigger=wf_in.event_trigger,
        conditions=wf_in.conditions,
        actions=wf_in.actions,
        is_active=wf_in.is_active,
    )
    db.add(wf)
    await db.flush()
    return ApiResponse(success=True, data=wf)


@router.get("", response_model=ApiResponse[List[WorkflowResponse]])
async def list_workflows(
    hospital_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.PLATFORM_ADMIN, UserRole.HOSPITAL_ADMIN)),
):
    scoped_hospital = hospital_id
    if current_user.role == UserRole.HOSPITAL_ADMIN and current_user.staff_profile:
        scoped_hospital = current_user.staff_profile.hospital_id

    query = select(Workflow)
    if scoped_hospital:
        query = query.where(Workflow.hospital_id == scoped_hospital)
    res = await db.execute(query)
    return ApiResponse(success=True, data=list(res.scalars().all()))


@router.get("/executions", response_model=ApiResponse[List[WorkflowExecutionResponse]])
async def list_workflow_executions(
    hospital_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.PLATFORM_ADMIN, UserRole.HOSPITAL_ADMIN)),
):
    scoped_hospital = hospital_id
    if current_user.role == UserRole.HOSPITAL_ADMIN and current_user.staff_profile:
        scoped_hospital = current_user.staff_profile.hospital_id

    query = select(WorkflowExecution).order_by(WorkflowExecution.created_at.desc()).limit(50)
    if scoped_hospital:
        query = query.where(WorkflowExecution.hospital_id == scoped_hospital)
    res = await db.execute(query)
    return ApiResponse(success=True, data=list(res.scalars().all()))
