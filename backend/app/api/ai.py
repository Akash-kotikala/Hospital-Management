import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.database import get_db
from app.db.models.auth import User
from app.db.models.ai import AIConversation, AIMessage
from app.api.deps import get_current_user, get_current_user_or_guest
from app.services.audit_service import AuditService
from app.ai.agent import ai_agent
from app.schemas.ai import (
    ChatRequest,
    ChatResponse,
    VoiceSessionRequest,
    VoiceSessionResponse,
    VoiceAudioProcessRequest,
    VoiceAudioProcessResponse,
)
from app.schemas.common import ApiResponse
from app.core.exceptions import EntityNotFoundException

router = APIRouter(prefix="/ai", tags=["AI Patient Access Agent & Voice"])


@router.post("/chat", response_model=ApiResponse[ChatResponse])
async def chat_with_agent(
    req: ChatRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_or_guest),
):
    """
    Interact with the administrative healthcare access agent:
    - Intent understanding & doctor discovery
    - Real availability check
    - Slot booking with EHR verification
    - Pre-visit intake questionnaire collection
    - Clinical safety boundary enforcement & emergency escalation
    """
    patient_id = current_user.patient_profile.id if current_user.patient_profile else None
    response = await ai_agent.chat(
        db=db,
        user_id=current_user.id,
        message_text=req.message,
        patient_id=patient_id,
        hospital_id=req.hospital_id,
        conversation_id=req.conversation_id,
    )
    return ApiResponse(success=True, data=response)


@router.post("/voice/session", response_model=ApiResponse[VoiceSessionResponse])
async def create_voice_session(
    req: VoiceSessionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_or_guest),
):
    """Initialize a voice intake session supporting browser Web Speech & streaming audio."""
    patient_id = current_user.patient_profile.id if current_user.patient_profile else None
    conv = await ai_agent.get_or_create_conversation(
        db,
        user_id=current_user.id,
        patient_id=patient_id,
        hospital_id=req.hospital_id,
        conversation_id=req.conversation_id,
        session_type="VOICE",
    )
    session_id = f"VOICE-{uuid.uuid4().hex[:8].upper()}"

    await AuditService.log_audit_event(
        db=db,
        action="VOICE_SESSION_INITIALIZED",
        resource_type="VOICE_SESSION",
        resource_id=session_id,
        actor_id=current_user.id,
        actor_role=current_user.role.value,
        details={"conversation_id": conv.id},
    )

    return ApiResponse(
        success=True,
        data=VoiceSessionResponse(
            session_id=session_id,
            conversation_id=conv.id,
            status="ACTIVE",
            supported_audio_formats=["audio/wav", "audio/webm", "browser_speech_api"],
        ),
    )


@router.post("/voice/process", response_model=ApiResponse[VoiceAudioProcessResponse])
async def process_voice_turn(
    req: VoiceAudioProcessRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user_or_guest),
):
    """Process a voice turn (audio transcript -> AI agent capabilities -> reply text)."""
    transcript = req.transcript or "I need an appointment."
    patient_id = current_user.patient_profile.id if current_user.patient_profile else None

    chat_resp = await ai_agent.chat(
        db=db,
        user_id=current_user.id,
        message_text=transcript,
        patient_id=patient_id,
        hospital_id=req.hospital_id,
        conversation_id=req.conversation_id,
    )

    return ApiResponse(
        success=True,
        data=VoiceAudioProcessResponse(
            transcript=transcript,
            reply_text=chat_resp.message,
            conversation_id=chat_resp.conversation_id,
            capabilities_called=chat_resp.capabilities_called,
        ),
    )


@router.get("/conversations", response_model=ApiResponse[List[dict]])
async def list_conversations(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List recent conversation sessions for authenticated user."""
    query = (
        select(AIConversation)
        .where(AIConversation.user_id == current_user.id)
        .order_by(AIConversation.created_at.desc())
        .limit(20)
    )
    result = await db.execute(query)
    convs = result.scalars().all()
    return ApiResponse(
        success=True,
        data=[
            {
                "id": c.id,
                "title": c.title,
                "session_type": c.session_type,
                "is_active": c.is_active,
                "created_at": c.created_at.isoformat(),
            }
            for c in convs
        ],
    )


@router.get("/conversations/{id}", response_model=ApiResponse[dict])
async def get_conversation(
    id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retrieve full conversation transcript and capability execution audit."""
    result = await db.execute(
        select(AIConversation)
        .options(
            selectinload(AIConversation.messages),
            selectinload(AIConversation.capabilities),
            selectinload(AIConversation.context),
        )
        .where(AIConversation.id == id)
    )
    conv = result.scalar_one_or_none()
    if not conv:
        raise EntityNotFoundException("AIConversation", id)

    return ApiResponse(
        success=True,
        data={
            "id": conv.id,
            "session_type": conv.session_type,
            "messages": [
                {
                    "id": m.id,
                    "sender": m.sender,
                    "content": m.content,
                    "created_at": m.created_at.isoformat(),
                    "tool_calls": m.tool_calls,
                }
                for m in conv.messages
            ],
            "capabilities": [
                {
                    "name": cap.capability_name,
                    "status": cap.status,
                    "duration_ms": cap.execution_duration_ms,
                    "created_at": cap.created_at.isoformat(),
                }
                for cap in conv.capabilities
            ],
        },
    )
