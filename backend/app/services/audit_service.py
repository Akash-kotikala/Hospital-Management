from typing import Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models.platform import AuditEvent, OperationalEvent
from app.core.logging import correlation_id_ctx, operation_id_ctx


class AuditService:
    @staticmethod
    async def log_audit_event(
        db: AsyncSession,
        action: str,
        resource_type: str,
        resource_id: Optional[str] = None,
        hospital_id: Optional[str] = None,
        user_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        correlation_id: Optional[str] = None,
        operation_id: Optional[str] = None,
        ip_address: Optional[str] = None,
    ) -> AuditEvent:
        event = AuditEvent(
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            hospital_id=hospital_id,
            user_id=user_id,
            details=details or {},
            correlation_id=correlation_id or correlation_id_ctx.get(),
            operation_id=operation_id or operation_id_ctx.get(),
            ip_address=ip_address,
        )
        db.add(event)
        await db.flush()
        return event

    @staticmethod
    async def log_operational_event(
        db: AsyncSession,
        event_type: str,
        service_name: str,
        severity: str = "INFO",
        details: Optional[Dict[str, Any]] = None,
        correlation_id: Optional[str] = None,
    ) -> OperationalEvent:
        event = OperationalEvent(
            event_type=event_type,
            service_name=service_name,
            severity=severity,
            details=details or {},
            correlation_id=correlation_id or correlation_id_ctx.get(),
        )
        db.add(event)
        await db.flush()
        return event
