from typing import Optional, Dict, Any
from fastapi import APIRouter, status
from app.integrations.mock_ehr import mock_ehr_connector
from app.db.models.enums import EHRSimulationMode
from app.schemas.integration import FailureModeRequest, FailureModeStatusResponse
from app.schemas.common import ApiResponse

router = APIRouter(prefix="/mock-ehr", tags=["Mock Healthcare System (EHR)"])


@router.get("/health")
async def mock_ehr_health():
    """Mock EHR service health check."""
    return {"status": "UP", "service": "MockEHR v1.4", "simulation": mock_ehr_connector.get_simulation_status()}


@router.post("/failure-mode", response_model=ApiResponse[FailureModeStatusResponse])
async def set_mock_ehr_failure_mode(req: FailureModeRequest):
    """Direct Mock EHR control endpoint to trigger intentional failure modes."""
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
            message=f"Simulation mode set to {req.mode.value}",
        ),
    )


@router.get("/providers")
async def get_ehr_providers():
    providers = await mock_ehr_connector.get_providers()
    return {"providers": providers}


@router.get("/facilities")
async def get_ehr_facilities():
    facilities = await mock_ehr_connector.get_facilities()
    return {"facilities": facilities}


@router.post("/appointments")
async def create_ehr_appointment(payload: Dict[str, Any]):
    return await mock_ehr_connector.create_appointment(payload)


@router.get("/appointments/{id}")
async def get_ehr_appointment(id: str):
    appt = await mock_ehr_connector.get_appointment(id)
    if not appt:
        return {"error": "Not found in EHR", "external_id": id}
    return appt


@router.post("/appointments/{id}/verify")
async def verify_ehr_appointment(id: str):
    return await mock_ehr_connector.verify_appointment(id)
