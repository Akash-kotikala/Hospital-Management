from typing import Optional, List, Dict, Any
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.notification import Notification
from app.db.models.enums import NotificationChannel, NotificationStatus
from app.core.logging import logger


class NotificationService:
    @staticmethod
    async def send_notification(
        db: AsyncSession,
        hospital_id: str,
        recipient: str,
        subject: str,
        content: str,
        channel: NotificationChannel = NotificationChannel.IN_APP,
        user_id: Optional[str] = None,
        patient_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Notification:
        notification = Notification(
            hospital_id=hospital_id,
            user_id=user_id,
            patient_id=patient_id,
            channel=channel,
            recipient=recipient,
            subject=subject,
            content=content,
            status=NotificationStatus.SENT,  # Simulated immediate delivery
            notification_metadata=metadata or {},
        )
        db.add(notification)
        await db.flush()

        logger.info(f"Notification [{channel.value}] dispatched to {recipient}: '{subject}'")
        return notification

    @staticmethod
    async def list_notifications(
        db: AsyncSession,
        hospital_id: Optional[str] = None,
        user_id: Optional[str] = None,
        patient_id: Optional[str] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> List[Notification]:
        query = select(Notification).offset(skip).limit(limit).order_by(Notification.created_at.desc())
        if hospital_id:
            query = query.where(Notification.hospital_id == hospital_id)
        if user_id:
            query = query.where(Notification.user_id == user_id)
        if patient_id:
            query = query.where(Notification.patient_id == patient_id)

        result = await db.execute(query)
        return list(result.scalars().all())
