import pytest
from app.services.appointment_service import AppointmentService
from app.db.models.enums import AppointmentStatus
from app.core.exceptions import InvalidStateTransitionException


def test_valid_and_invalid_state_transitions():
    # Valid transitions
    AppointmentService.validate_transition(AppointmentStatus.PENDING, AppointmentStatus.CONFIRMED)
    AppointmentService.validate_transition(AppointmentStatus.CONFIRMED, AppointmentStatus.RESCHEDULED)
    AppointmentService.validate_transition(AppointmentStatus.CONFIRMED, AppointmentStatus.CANCELLED)
    AppointmentService.validate_transition(AppointmentStatus.SYNCHRONIZATION_PENDING, AppointmentStatus.CONFIRMED)

    # Invalid transitions
    with pytest.raises(InvalidStateTransitionException):
        AppointmentService.validate_transition(AppointmentStatus.CANCELLED, AppointmentStatus.CONFIRMED)

    with pytest.raises(InvalidStateTransitionException):
        AppointmentService.validate_transition(AppointmentStatus.COMPLETED, AppointmentStatus.PENDING)

    with pytest.raises(InvalidStateTransitionException):
        AppointmentService.validate_transition(AppointmentStatus.FAILED, AppointmentStatus.CONFIRMED)
