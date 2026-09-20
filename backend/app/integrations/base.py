from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List


class HealthcareConnector(ABC):
    """Abstract interface for Healthcare Systems / EHR connectors."""

    @abstractmethod
    async def lookup_patient(self, demographics: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        pass

    @abstractmethod
    async def get_providers(self, facility_id: Optional[str] = None) -> List[Dict[str, Any]]:
        pass

    @abstractmethod
    async def get_facilities(self) -> List[Dict[str, Any]]:
        pass

    @abstractmethod
    async def create_appointment(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Creates an appointment in the external EHR."""
        pass

    @abstractmethod
    async def get_appointment(self, external_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves appointment details from the external EHR."""
        pass

    @abstractmethod
    async def update_appointment(self, external_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Updates/reschedules an appointment in the external EHR."""
        pass

    @abstractmethod
    async def cancel_appointment(self, external_id: str, reason: str) -> Dict[str, Any]:
        """Cancels an appointment in the external EHR."""
        pass

    @abstractmethod
    async def verify_appointment(self, external_id: str) -> Dict[str, Any]:
        """Verifies appointment existence and confirmation status in the external EHR."""
        pass
