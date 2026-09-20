from typing import Optional, Any, Dict
from fastapi import status


class AppException(Exception):
    """Base application exception mapped to standardized API error response."""
    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = status.HTTP_400_BAD_REQUEST,
        details: Optional[Dict[str, Any]] = None,
        correlation_id: Optional[str] = None,
    ):
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        self.correlation_id = correlation_id
        super().__init__(message)


class AuthenticationException(AppException):
    def __init__(self, message: str = "Invalid authentication credentials", code: str = "AUTHENTICATION_FAILED"):
        super().__init__(code=code, message=message, status_code=status.HTTP_401_UNAUTHORIZED)


class AuthorizationException(AppException):
    def __init__(self, message: str = "You do not have permission to perform this action", code: str = "PERMISSION_DENIED"):
        super().__init__(code=code, message=message, status_code=status.HTTP_403_FORBIDDEN)


class TenantAccessDeniedException(AppException):
    def __init__(self, message: str = "Access to requested tenant resource is forbidden", code: str = "TENANT_ACCESS_DENIED"):
        super().__init__(code=code, message=message, status_code=status.HTTP_403_FORBIDDEN)


class EntityNotFoundException(AppException):
    def __init__(self, entity_name: str, entity_id: Any, code: str = "RESOURCE_NOT_FOUND"):
        super().__init__(
            code=code,
            message=f"{entity_name} with id '{entity_id}' was not found.",
            status_code=status.HTTP_404_NOT_FOUND,
        )


class SlotUnavailableException(AppException):
    def __init__(self, message: str = "The selected appointment slot is no longer available.", code: str = "SLOT_NO_LONGER_AVAILABLE"):
        super().__init__(code=code, message=message, status_code=status.HTTP_409_CONFLICT)


class InvalidStateTransitionException(AppException):
    def __init__(self, current_state: str, target_state: str, code: str = "INVALID_STATE_TRANSITION"):
        super().__init__(
            code=code,
            message=f"Cannot transition appointment from state '{current_state}' to '{target_state}'.",
            status_code=422,
        )


class EHRIntegrationException(AppException):
    def __init__(self, message: str, code: str = "EHR_INTEGRATION_ERROR", status_code: int = status.HTTP_502_BAD_GATEWAY):
        super().__init__(code=code, message=message, status_code=status_code)


class EHRTimeoutException(EHRIntegrationException):
    def __init__(self, message: str = "EHR external system timed out during operation.", code: str = "EHR_TIMEOUT"):
        super().__init__(message=message, code=code, status_code=status.HTTP_504_GATEWAY_TIMEOUT)
