from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.security import get_password_hash, verify_password, create_access_token
from app.core.exceptions import AuthenticationException, AppException
from app.db.models.auth import User, HospitalStaff
from app.db.models.patient import Patient
from app.db.models.doctor import Doctor
from app.db.models.enums import UserRole
from app.schemas.auth import UserCreate, UserLogin, UserResponse, TokenResponse
from app.services.audit_service import AuditService


class AuthService:
    @staticmethod
    async def register_user(db: AsyncSession, user_in: UserCreate) -> UserResponse:
        # Check if email exists
        existing = await db.execute(select(User).where(User.email == user_in.email))
        if existing.scalar_one_or_none():
            raise AppException(
                code="EMAIL_ALREADY_EXISTS",
                message=f"A user with email '{user_in.email}' is already registered."
            )

        hashed_pw = get_password_hash(user_in.password)
        user = User(
            email=user_in.email,
            hashed_password=hashed_pw,
            full_name=user_in.full_name,
            role=user_in.role,
            phone=user_in.phone,
        )
        db.add(user)
        await db.flush()

        hospital_id = user_in.hospital_id
        patient_id = None
        doctor_id = None

        if user_in.role == UserRole.HOSPITAL_ADMIN:
            if not hospital_id:
                raise AppException(code="HOSPITAL_ID_REQUIRED", message="Hospital ID is required for Hospital Admin registration.")
            staff = HospitalStaff(
                user_id=user.id,
                hospital_id=hospital_id,
                role_title="Hospital Administrator",
            )
            db.add(staff)
            await db.flush()

        elif user_in.role == UserRole.PATIENT:
            names = user_in.full_name.split(" ", 1)
            first_name = names[0]
            last_name = names[1] if len(names) > 1 else ""
            patient = Patient(
                user_id=user.id,
                first_name=first_name,
                last_name=last_name,
                email=user_in.email,
                phone=user_in.phone or "Unknown",
                primary_hospital_id=hospital_id,
            )
            db.add(patient)
            await db.flush()
            patient_id = patient.id

        await AuditService.log_audit_event(
            db=db,
            action="USER_REGISTERED",
            resource_type="USER",
            resource_id=user.id,
            hospital_id=hospital_id,
            user_id=user.id,
            details={"email": user.email, "role": user.role.value}
        )

        return UserResponse(
            id=user.id,
            email=user.email,
            full_name=user.full_name,
            role=user.role,
            is_active=user.is_active,
            phone=user.phone,
            hospital_id=hospital_id,
            patient_id=patient_id,
            doctor_id=doctor_id,
        )

    @staticmethod
    async def authenticate_user(db: AsyncSession, login_data: UserLogin) -> TokenResponse:
        result = await db.execute(
            select(User)
            .options(
                selectinload(User.staff_profile),
                selectinload(User.doctor_profile),
                selectinload(User.patient_profile),
            )
            .where(User.email == login_data.email)
        )
        user = result.scalar_one_or_none()
        if not user or not verify_password(login_data.password, user.hashed_password):
            raise AuthenticationException("Invalid email or password")

        if not user.is_active:
            raise AuthenticationException("Account is suspended or deactivated")

        hospital_id = None
        patient_id = None
        doctor_id = None

        if user.staff_profile:
            hospital_id = user.staff_profile.hospital_id
        elif user.doctor_profile:
            hospital_id = user.doctor_profile.hospital_id
            doctor_id = user.doctor_profile.id
        elif user.patient_profile:
            patient_id = user.patient_profile.id
            hospital_id = user.patient_profile.primary_hospital_id

        extra_claims = {
            "role": user.role.value,
            "hospital_id": hospital_id,
            "patient_id": patient_id,
            "doctor_id": doctor_id,
        }
        token = create_access_token(subject=user.id, extra_claims=extra_claims)

        user_resp = UserResponse(
            id=user.id,
            email=user.email,
            full_name=user.full_name,
            role=user.role,
            is_active=user.is_active,
            phone=user.phone,
            hospital_id=hospital_id,
            patient_id=patient_id,
            doctor_id=doctor_id,
        )

        await AuditService.log_audit_event(
            db=db,
            action="USER_LOGIN_SUCCESS",
            resource_type="USER",
            resource_id=user.id,
            hospital_id=hospital_id,
            user_id=user.id,
            details={"email": user.email}
        )

        return TokenResponse(access_token=token, user=user_resp)
