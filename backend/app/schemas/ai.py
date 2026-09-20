from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class CapabilityCallInfo(BaseModel):
    name: str
    arguments: Dict[str, Any]
    result: Optional[Dict[str, Any]] = None
    status: str = "SUCCESS"


class ChatRequest(BaseModel):
    message: str
    conversation_id: Optional[str] = None
    hospital_id: Optional[str] = None


class ChatResponse(BaseModel):
    conversation_id: str
    message: str
    capabilities_called: List[CapabilityCallInfo] = Field(default_factory=list)
    context_state: Dict[str, Any] = Field(default_factory=dict)
    is_emergency_escalation: bool = False
    requires_human_transfer: bool = False
    timeline_event: Optional[str] = None


class VoiceSessionRequest(BaseModel):
    hospital_id: Optional[str] = None
    conversation_id: Optional[str] = None


class VoiceSessionResponse(BaseModel):
    session_id: str
    conversation_id: str
    status: str = "ACTIVE"
    mode: str = "BROWSER_SPEECH"  # or GEMINI_LIVE / SERVER_STT


class VoiceAudioProcessRequest(BaseModel):
    audio_base64: Optional[str] = None
    transcript: Optional[str] = None
    conversation_id: Optional[str] = None
    hospital_id: Optional[str] = None


class VoiceAudioProcessResponse(BaseModel):
    transcript: str
    reply_text: str
    audio_base64: Optional[str] = None
    conversation_id: str
    capabilities_called: List[CapabilityCallInfo] = Field(default_factory=list)
