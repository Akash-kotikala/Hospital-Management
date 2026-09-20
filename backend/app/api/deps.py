import uuid
from typing import Optional, List, Callable
from fastapi import Depends, Header, Request
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.security import decode_access_token
from app.core.exceptions import AuthenticationException, AuthorizationException, TenantAccessDeniedException
from app.core.logging import correlation_id_ctx, operation_id_ctx
from app.db.database import get_db
from app.db.models.auth import User, HospitalStaff
from app.db.models.enums import UserRole
from app.db.models.doctor import Doctor
from app.db.models.patient import Patient

oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/auth/login", auto_error=False)


async def get_correlation_context(
    x_correlation_id: Optional[str] = Header(None, alias="X-Correlation-ID"),
    x_operation_id: Optional[str] = Header(None, alias="X-Operation-ID"),
) -> dict:
    corr_id = x_correlation_id or str(uuid.uuid4())
    op_id = x_operation_id or str(uuid.uuid4())
    correlation_id_ctx.set(corr_id)
    operation_id_ctx.set(op_id)
    return {"correlation_id": corr_id, "operation_id": op_id}


async def get_current_user(
    token: Optional[str] = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
    _ctx: dict = Depends(get_correlation_context),
) -> User:
    if not token:
        raise AuthenticationException("Authentication required", code="MISSING_TOKEN")

    payload = decode_access_token(token)
    user_id: Optional[str] = payload.get("sub")
    if not user_id:
        raise AuthenticationException("Token payload missing subject identifier")

    result = await db.execute(
        select(User)
        .options(
            selectinload(User.staff_profile),
            selectinload(User.doctor_profile),
            selectinload(User.patient_profile),
        )
        .where(User.id == user_id)
    )
    user = result.scalar_one_or_none()
    if not user:
        raise AuthenticationException("User associated with token no longer exists")
    if not user.is_active:
        raise AuthenticationException("User account is deactivated")

    return user


async def get_current_user_or_guest(
    token: Optional[str] = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
    _ctx: dict = Depends(get_correlation_context),
) -> User:
    """Returns the authenticated user, or falls back to demo patient Jane Doe for patient intake flows."""
    if token:
        try:
            payload = decode_access_token(token)
            user_id: Optional[str] = payload.get("sub")
            if user_id:
                result = await db.execute(
                    select(User)
                    .options(
                        selectinload(User.staff_profile),
                        selectinload(User.doctor_profile),
                        selectinload(User.patient_profile),
                    )
                    .where(User.id == user_id)
                )
                user = result.scalar_one_or_none()
                if user and user.is_active:
                    return user
        except Exception:
            pass

    # Fallback to demo patient Jane Doe
    result = await db.execute(
        select(User)
        .options(
            selectinload(User.staff_profile),
            selectinload(User.doctor_profile),
            selectinload(User.patient_profile),
        )
        .where(User.email == "jane.doe@example.com")
    )
    user = result.scalar_one_or_none()
    if user:
        return user

    # Auto-seed if database is brand new
    try:
        from app.db.seed import seed_database
        await seed_database()
        result = await db.execute(
            select(User)
            .options(
                selectinload(User.staff_profile),
                selectinload(User.doctor_profile),
                selectinload(User.patient_profile),
            )
            .where(User.email == "jane.doe@example.com")
        )
        user = result.scalar_one_or_none()
        if user:
            return user
    except Exception:
        pass

    raise AuthenticationException("Unable to resolve user session", code="SESSION_FAILED")


def require_role(*allowed_roles: UserRole) -> Callable:
    async def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed_roles:
            raise AuthorizationException(
                f"Role '{current_user.role.value}' does not have permission. Required one of: {[r.value for r in allowed_roles]}"
            )
        return current_user
    return role_checker


async def verify_tenant_access(
    hospital_id: str,
    current_user: User,
) -> bool:
    """Strict tenant isolation check."""
    # Platform Admin can view and manage all hospitals
    if current_user.role == UserRole.PLATFORM_ADMIN:
        return True

    # Hospital Admin must belong to the exact hospital
    if current_user.role == UserRole.HOSPITAL_ADMIN:
        if current_user.staff_profile and current_user.staff_profile.hospital_id == hospital_id:
            return True
        raise TenantAccessDeniedException(f"Hospital Admin does not have access to hospital '{hospital_id}'")

    # Doctor must belong to the exact hospital
    if current_user.role == UserRole.DOCTOR:
        if current_user.doctor_profile and current_user.doctor_profile.hospital_id == hospital_id:
            return True
        raise TenantAccessDeniedException(f"Doctor does not have access to hospital '{hospital_id}'")

    # Patients are restricted at the resource level (their own appointments/records)
    return True
