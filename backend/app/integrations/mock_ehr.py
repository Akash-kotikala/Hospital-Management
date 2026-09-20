import asyncio
import uuid
import datetime
from typing import Dict, Any, Optional, List
from app.integrations.base import HealthcareConnector
from app.core.exceptions import EHRIntegrationException, EHRTimeoutException
from app.db.models.enums import EHRSimulationMode
from app.core.logging import logger


class MockEHRConnector(HealthcareConnector):
    """
    Realistic Mock EHR implementation supporting external patient/provider lookup,
    appointment lifecycle, and deliberate failure modes (TIMEOUT, UNKNOWN_OUTCOME, etc.)
    for operational failure demonstration.
    """

    def __init__(self):
        self._simulation_mode: EHRSimulationMode = EHRSimulationMode.NORMAL
        self._target_operation: str = "CREATE_APPOINTMENT"
        self._active_countdown: int = 0

        # In-memory EHR store for external records
        self._appointments: Dict[str, Dict[str, Any]] = {}
        self._patients: Dict[str, Dict[str, Any]] = {
            "EHR-PAT-001": {
                "id": "EHR-PAT-001",
                "name": "Jane Doe",
                "dob": "1988-04-12",
                "gender": "Female",
                "insurance_provider": "BlueCross Shield",
                "policy_number": "BCS-992182",
            }
        }
        self._providers: Dict[str, Dict[str, Any]] = {
            "EHR-DOC-RAO": {"id": "EHR-DOC-RAO", "name": "Dr. Marcus Rao", "specialty": "Orthopedics"},
            "EHR-DOC-CHEN": {"id": "EHR-DOC-CHEN", "name": "Dr. Sarah Chen", "specialty": "Cardiology"},
        }
        self._facilities: List[Dict[str, Any]] = [
            {"id": "EHR-FAC-01", "name": "Metro General Hospital", "npi": "1098765432"},
            {"id": "EHR-FAC-02", "name": "Apex Healthcare Pavilion", "npi": "1987654321"},
        ]

    def set_simulation_mode(self, mode: EHRSimulationMode, target_operation: str = "CREATE_APPOINTMENT", countdown: int = 1):
        self._simulation_mode = mode
        self._target_operation = target_operation
        self._active_countdown = countdown
        logger.warning(f"Mock EHR simulation mode set to {mode.value} (target={target_operation}, countdown={countdown})")

    def get_simulation_status(self) -> Dict[str, Any]:
        return {
            "current_mode": self._simulation_mode.value,
            "target_operation": self._target_operation,
            "active_until_resets": self._active_countdown,
        }

    def _check_simulation_trigger(self, operation: str, appointment_payload: Optional[Dict[str, Any]] = None) -> Optional[str]:
        if self._active_countdown > 0 and (self._target_operation == operation or self._target_operation == "ALL"):
            self._active_countdown -= 1
            mode = self._simulation_mode
            if self._active_countdown == 0:
                self._simulation_mode = EHRSimulationMode.NORMAL
            return mode.value
        return None

    async def lookup_patient(self, demographics: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        for pat in self._patients.values():
            if demographics.get("phone") and pat.get("phone") == demographics["phone"]:
                return pat
            if demographics.get("name") and pat.get("name", "").lower() == demographics["name"].lower():
                return pat
        return list(self._patients.values())[0] if self._patients else None

    async def get_providers(self, facility_id: Optional[str] = None) -> List[Dict[str, Any]]:
        return list(self._providers.values())

    async def get_facilities(self) -> List[Dict[str, Any]]:
        return self._facilities

    async def create_appointment(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        triggered_mode = self._check_simulation_trigger("CREATE_APPOINTMENT", payload)

        if triggered_mode == EHRSimulationMode.TIMEOUT.value:
            # Simulate real latency before timeout exception
            await asyncio.sleep(0.5)
            raise EHRTimeoutException("Mock EHR request timed out during CREATE_APPOINTMENT.")

        if triggered_mode == EHRSimulationMode.UNKNOWN_OUTCOME.value:
            # External system processed and persisted the record, but client received network timeout
            ext_id = f"EHR-APPT-{uuid.uuid4().hex[:8].upper()}"
            record = {
                "external_id": ext_id,
                "status": "CONFIRMED",
                "doctor_id": payload.get("doctor_id"),
                "patient_id": payload.get("patient_id"),
                "start_time": payload.get("start_time"),
                "end_time": payload.get("end_time"),
                "idempotency_key": payload.get("idempotency_key"),
                "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            }
            self._appointments[ext_id] = record
            await asyncio.sleep(0.5)
            raise EHRTimeoutException("Connection timed out waiting for gateway response (UNKNOWN_OUTCOME).")

        if triggered_mode == EHRSimulationMode.AUTH_ERROR.value:
            raise EHRIntegrationException("EHR authorization credentials rejected.", code="EHR_AUTH_ERROR", status_code=401)

        if triggered_mode == EHRSimulationMode.SLOT_CONFLICT.value:
            raise EHRIntegrationException("EHR reported schedule conflict for provider.", code="EHR_SLOT_CONFLICT", status_code=409)

        # Normal booking execution
        ext_id = f"EHR-APPT-{uuid.uuid4().hex[:8].upper()}"
        record = {
            "external_id": ext_id,
            "status": "CONFIRMED",
            "doctor_id": payload.get("doctor_id"),
            "patient_id": payload.get("patient_id"),
            "start_time": payload.get("start_time"),
            "end_time": payload.get("end_time"),
            "idempotency_key": payload.get("idempotency_key"),
            "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }
        self._appointments[ext_id] = record
        return record

    async def get_appointment(self, external_id: str) -> Optional[Dict[str, Any]]:
        return self._appointments.get(external_id)

    async def find_appointment_by_idempotency_key(self, idempotency_key: str) -> Optional[Dict[str, Any]]:
        """Used during timeout recovery to safely verify whether appointment was created in EHR."""
        for appt in self._appointments.values():
            if appt.get("idempotency_key") == idempotency_key:
                return appt
        return None

    async def update_appointment(self, external_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        if external_id not in self._appointments:
            raise EHRIntegrationException(f"Appointment {external_id} not found in Mock EHR.", status_code=404)
        record = self._appointments[external_id]
        record["start_time"] = payload.get("start_time", record["start_time"])
        record["end_time"] = payload.get("end_time", record["end_time"])
        record["status"] = "RESCHEDULED"
        record["updated_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        return record

    async def cancel_appointment(self, external_id: str, reason: str) -> Dict[str, Any]:
        if external_id not in self._appointments:
            raise EHRIntegrationException(f"Appointment {external_id} not found in Mock EHR.", status_code=404)
        record = self._appointments[external_id]
        record["status"] = "CANCELLED"
        record["cancellation_reason"] = reason
        record["cancelled_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        return record

    async def verify_appointment(self, external_id: str) -> Dict[str, Any]:
        """External verification step."""
        appt = self._appointments.get(external_id)
        if not appt:
            return {"verified": False, "status": "NOT_FOUND"}
        return {
            "verified": True,
            "status": appt.get("status"),
            "external_id": external_id,
            "start_time": appt.get("start_time"),
            "end_time": appt.get("end_time"),
        }


# Global Mock EHR instance
mock_ehr_connector = MockEHRConnector()
