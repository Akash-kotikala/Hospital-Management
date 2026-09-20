from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional


class LLMProvider(ABC):
    """Abstract interface for LLM providers."""

    @abstractmethod
    async def generate_response(
        self,
        messages: List[Dict[str, Any]],
        system_instruction: str,
        capabilities: List[Dict[str, Any]],
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Processes conversation messages, executes function calls if requested,
        and returns response text, capability executions, and state updates.
        """
        pass
