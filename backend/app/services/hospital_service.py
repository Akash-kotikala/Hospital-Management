from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import EntityNotFoundException, AppException
from app.db.models.hospital import Hospital, Department, Specialty
from app.db.models.enums import HospitalStatus
from app.schemas.hospital import HospitalCreate, HospitalUpdate, DepartmentCreate, SpecialtyCreate
from app.services.audit_service import AuditService


class HospitalService:
    @staticmethod
    async def create_hospital(db: AsyncSession, hospital_in: HospitalCreate) -> Hospital:
        # Check slug uniqueness
        existing = await db.execute(select(Hospital).where(Hospital.slug == hospital_in.slug))
        if existing.scalar_one_or_none():
            raise AppException(
                code="HOSPITAL_SLUG_EXISTS",
                message=f"A hospital with slug '{hospital_in.slug}' already exists."
            )

        hospital = Hospital(
            name=hospital_in.name,
            slug=hospital_in.slug,
            address=hospital_in.address,
            phone=hospital_in.phone,
            email=hospital_in.email,
            website=hospital_in.website,
            status=HospitalStatus.DRAFT,
            configuration=hospital_in.configuration or {},
        )
        db.add(hospital)
        await db.flush()

        await AuditService.log_audit_event(
            db=db,
            action="HOSPITAL_CREATED",
            resource_type="HOSPITAL",
            resource_id=hospital.id,
            hospital_id=hospital.id,
            details={"name": hospital.name, "status": hospital.status.value}
        )
        return hospital

    @staticmethod
    async def get_hospital(db: AsyncSession, hospital_id: str) -> Hospital:
        result = await db.execute(
            select(Hospital)
            .options(
                selectinload(Hospital.departments),
                selectinload(Hospital.specialties),
            )
            .where(Hospital.id == hospital_id)
        )
        hospital = result.scalar_one_or_none()
        if not hospital:
            raise EntityNotFoundException("Hospital", hospital_id)
        return hospital

    @staticmethod
    async def list_hospitals(
        db: AsyncSession,
        status: Optional[HospitalStatus] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> List[Hospital]:
        query = (
            select(Hospital)
            .options(
                selectinload(Hospital.departments),
                selectinload(Hospital.specialties),
            )
            .offset(skip)
            .limit(limit)
        )
        if status:
            query = query.where(Hospital.status == status)
        result = await db.execute(query)
        return list(result.scalars().all())

    @staticmethod
    async def submit_hospital(db: AsyncSession, hospital_id: str) -> Hospital:
        hospital = await HospitalService.get_hospital(db, hospital_id)
        if hospital.status not in (HospitalStatus.DRAFT, HospitalStatus.REJECTED):
            raise AppException(
                code="INVALID_HOSPITAL_STATE",
                message=f"Hospital cannot be submitted from status '{hospital.status.value}'"
            )
        hospital.status = HospitalStatus.SUBMITTED
        await db.flush()

        await AuditService.log_audit_event(
            db=db,
            action="HOSPITAL_SUBMITTED",
            resource_type="HOSPITAL",
            resource_id=hospital.id,
            hospital_id=hospital.id,
            details={"new_status": hospital.status.value}
        )
        return hospital

    @staticmethod
    async def approve_hospital(db: AsyncSession, hospital_id: str, admin_user_id: str) -> Hospital:
        hospital = await HospitalService.get_hospital(db, hospital_id)
        hospital.status = HospitalStatus.APPROVED
        await db.flush()

        await AuditService.log_audit_event(
            db=db,
            action="HOSPITAL_APPROVED",
            resource_type="HOSPITAL",
            resource_id=hospital.id,
            hospital_id=hospital.id,
            user_id=admin_user_id,
            details={"approved_by": admin_user_id}
        )
        return hospital

    @staticmethod
    async def reject_hospital(db: AsyncSession, hospital_id: str, admin_user_id: str, reason: str) -> Hospital:
        hospital = await HospitalService.get_hospital(db, hospital_id)
        hospital.status = HospitalStatus.REJECTED
        await db.flush()

        await AuditService.log_audit_event(
            db=db,
            action="HOSPITAL_REJECTED",
            resource_type="HOSPITAL",
            resource_id=hospital.id,
            hospital_id=hospital.id,
            user_id=admin_user_id,
            details={"rejected_by": admin_user_id, "reason": reason}
        )
        return hospital

    @staticmethod
    async def add_department(db: AsyncSession, hospital_id: str, dept_in: DepartmentCreate) -> Department:
        hospital = await HospitalService.get_hospital(db, hospital_id)
        department = Department(
            hospital_id=hospital.id,
            name=dept_in.name,
            code=dept_in.code,
            description=dept_in.description,
        )
        db.add(department)
        await db.flush()
        return department

    @staticmethod
    async def add_specialty(db: AsyncSession, hospital_id: str, spec_in: SpecialtyCreate) -> Specialty:
        specialty = Specialty(
            hospital_id=hospital_id,
            name=spec_in.name,
            code=spec_in.code,
            description=spec_in.description,
        )
        db.add(specialty)
        await db.flush()
        return specialty
