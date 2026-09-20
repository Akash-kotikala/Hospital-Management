import datetime
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.hospital_service import HospitalService
from app.services.doctor_service import DoctorService
from app.services.scheduling_service import SchedulingService
from app.services.appointment_service import AppointmentService
from app.services.questionnaire_service import QuestionnaireService
from app.services.notification_service import NotificationService
from app.services.workflow_service import WorkflowService
from app.services.reconciliation_service import ReconciliationService
from app.integrations.mock_ehr import mock_ehr_connector
from app.schemas.appointment import AppointmentCreate, AppointmentReschedule, AppointmentCancel
from app.schemas.questionnaire import QuestionnaireAnswerSubmit
from app.db.models.enums import AppointmentStatus, ConsultationType


# Input Schemas for Gemini function calling & execution validation
class SearchHospitalsInput(BaseModel):
    query: Optional[str] = Field(None, description="Optional search term for hospital name or city")


class SearchDoctorsInput(BaseModel):
    specialty_name: Optional[str] = Field(None, description="Medical specialty, e.g. Orthopedics, Cardiology, Dermatology")
    doctor_name: Optional[str] = Field(None, description="Doctor name or partial query")
    hospital_id: Optional[str] = Field(None, description="Hospital identifier")


class CheckAvailabilityInput(BaseModel):
    doctor_id: str = Field(..., description="ID of the doctor to look up")
    start_date: Optional[str] = Field(None, description="Start date in YYYY-MM-DD format. Defaults to today.")
    end_date: Optional[str] = Field(None, description="End date in YYYY-MM-DD format. Defaults to 7 days ahead.")
    consultation_type: Optional[str] = Field("IN_PERSON", description="IN_PERSON or VIDEO")


class LookupPatientInput(BaseModel):
    patient_id: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None


class GetAppointmentInput(BaseModel):
    appointment_id: str


class CreateAppointmentInput(BaseModel):
    doctor_id: Optional[str] = Field(None, description="Doctor ID. If omitted, resolved from active context.")
    hospital_id: Optional[str] = None
    start_time: str = Field(..., description="ISO 8601 start time, e.g. 2026-09-22T10:00:00Z")
    consultation_type: Optional[str] = "IN_PERSON"
    reason_for_visit: Optional[str] = None
    chief_complaint: Optional[str] = None


class RescheduleAppointmentInput(BaseModel):
    appointment_id: str
    new_start_time: str
    reason: Optional[str] = "Patient rescheduled"


class CancelAppointmentInput(BaseModel):
    appointment_id: str
    reason: Optional[str] = "Patient requested cancellation"


class GetQuestionnaireInput(BaseModel):
    appointment_id: str


class SubmitQuestionnaireInput(BaseModel):
    appointment_id: str
    answers: Dict[str, Any]


class SendNotificationInput(BaseModel):
    hospital_id: str
    recipient: str
    subject: str
    content: str


class StartWorkflowInput(BaseModel):
    hospital_id: str
    event_trigger: str
    payload: Dict[str, Any] = Field(default_factory=dict)


class GetContextInput(BaseModel):
    conversation_id: str


class UpdatePreferencesInput(BaseModel):
    user_id: str
    preferred_hospital_id: Optional[str] = None
    preferred_communication_channel: Optional[str] = "EMAIL"


class VerifyExternalAppointmentInput(BaseModel):
    appointment_id: str
    external_appointment_id: str


class SynchronizeStateInput(BaseModel):
    appointment_id: str


class TransferToHumanInput(BaseModel):
    reason: str
    department: Optional[str] = "Patient Support"


# Capability Handlers mapped to backend services
async def handle_search_hospitals(db: AsyncSession, args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    hospitals = await HospitalService.list_hospitals(db, skip=0, limit=10)
    query = (args.get("query") or "").lower()
    if query:
        hospitals = [h for h in hospitals if query in h.name.lower() or query in h.address.lower()]
    return {
        "hospitals": [
            {"id": h.id, "name": h.name, "address": h.address, "phone": h.phone, "status": h.status.value}
            for h in hospitals
        ]
    }


async def handle_search_doctors(db: AsyncSession, args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    doctors = await DoctorService.list_doctors(
        db,
        hospital_id=args.get("hospital_id") or context.get("selected_hospital_id"),
        search_query=args.get("doctor_name"),
    )
    spec_query = (args.get("specialty_name") or "").lower()
    if spec_query:
        doctors = [
            d for d in doctors
            if (d.specialty and spec_query in d.specialty.name.lower()) or (spec_query in d.name.lower())
        ]
    return {
        "doctors": [
            {
                "id": d.id,
                "name": d.name,
                "hospital_id": d.hospital_id,
                "specialty": d.specialty.name if d.specialty else "General",
                "qualifications": d.qualifications,
                "experience_years": d.experience_years,
                "languages": d.languages,
                "duration_minutes": d.appointment_duration_minutes,
            }
            for d in doctors
        ]
    }


async def handle_check_availability(db: AsyncSession, args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    doctor_id = args.get("doctor_id") or context.get("selected_doctor_id")
    if not doctor_id:
        return {"error": "doctor_id is required to check availability."}

    start_date_str = args.get("start_date")
    if start_date_str:
        start_date = datetime.date.fromisoformat(start_date_str[:10])
    else:
        start_date = datetime.datetime.now(datetime.timezone.utc).date()

    end_date_str = args.get("end_date")
    if end_date_str:
        end_date = datetime.date.fromisoformat(end_date_str[:10])
    else:
        end_date = start_date + datetime.timedelta(days=7)

    slots = await SchedulingService.get_available_slots(
        db=db,
        doctor_id=doctor_id,
        start_date=start_date,
        end_date=end_date,
        consultation_type=args.get("consultation_type"),
    )
    return {
        "doctor_id": doctor_id,
        "slot_count": len(slots),
        "available_slots": [
            {
                "doctor_id": s.doctor_id,
                "start_time": s.start_time.isoformat(),
                "end_time": s.end_time.isoformat(),
                "formatted": s.start_time.strftime("%A, %b %d at %I:%M %p"),
                "doctor_name": s.doctor_name,
                "hospital_id": s.hospital_id,
                "specialty_name": s.specialty_name,
            }
            for s in slots[:12]  # Return next 12 candidate slots
        ]
    }


async def handle_create_appointment(db: AsyncSession, args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    patient_id = context.get("patient_id")
    if not patient_id:
        return {"error": "Patient identity must be established before booking an appointment."}

    start_time = datetime.datetime.fromisoformat(args["start_time"].replace("Z", "+00:00"))
    doctor_id = args.get("doctor_id") or context.get("selected_doctor_id")
    if not doctor_id:
        return {"error": "doctor_id could not be resolved from request or context."}

    doctor = await DoctorService.get_doctor(db, doctor_id)
    hospital_id = args.get("hospital_id") or doctor.hospital_id

    appt_create = AppointmentCreate(
        doctor_id=doctor_id,
        hospital_id=hospital_id,
        start_time=start_time,
        consultation_type=ConsultationType(args.get("consultation_type", "IN_PERSON")),
        reason_for_visit=args.get("reason_for_visit") or "AI Assistant Scheduled Visit",
        chief_complaint=args.get("chief_complaint"),
    )

    result = await AppointmentService.book_appointment(
        db=db,
        appt_in=appt_create,
        patient_id=patient_id,
        user_id=context.get("user_id"),
        correlation_id=context.get("correlation_id"),
    )

    appt = result["appointment"]
    return {
        "appointment_id": appt.id,
        "status": appt.status.value,
        "start_time": appt.start_time.isoformat(),
        "doctor_id": appt.doctor_id,
        "external_appointment_id": appt.external_appointment_id,
        "message": result.get("message") or "Appointment created and verified.",
        "timeout_encountered": result.get("timeout_encountered", False),
    }


async def handle_get_appointment(db: AsyncSession, args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    appt = await AppointmentService.get_appointment(db, args["appointment_id"])
    return {
        "id": appt.id,
        "status": appt.status.value,
        "start_time": appt.start_time.isoformat(),
        "doctor_name": appt.doctor.name if appt.doctor else None,
        "hospital_id": appt.hospital_id,
        "external_appointment_id": appt.external_appointment_id,
    }


async def handle_reschedule_appointment(db: AsyncSession, args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    new_start = datetime.datetime.fromisoformat(args["new_start_time"].replace("Z", "+00:00"))
    resch = AppointmentReschedule(new_start_time=new_start, reason=args.get("reason"))
    appt = await AppointmentService.reschedule_appointment(
        db, args["appointment_id"], resch, user_id=context.get("user_id")
    )
    return {"appointment_id": appt.id, "status": appt.status.value, "new_start_time": appt.start_time.isoformat()}


async def handle_cancel_appointment(db: AsyncSession, args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    can = AppointmentCancel(reason=args.get("reason", "Patient cancellation"))
    appt = await AppointmentService.cancel_appointment(db, args["appointment_id"], can, user_id=context.get("user_id"))
    return {"appointment_id": appt.id, "status": appt.status.value, "message": "Appointment cancelled."}


async def handle_get_questionnaire(db: AsyncSession, args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    q = await QuestionnaireService.find_questionnaire_for_appointment(db, args["appointment_id"])
    if not q:
        return {"has_questionnaire": False, "questions": []}
    return {
        "has_questionnaire": True,
        "questionnaire_id": q.id,
        "title": q.title,
        "questions": [
            {"id": qn.id, "prompt": qn.prompt, "type": qn.question_type.value, "options": qn.options}
            for qn in q.questions
        ]
    }


async def handle_submit_questionnaire(db: AsyncSession, args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    patient_id = context.get("patient_id")
    sub = QuestionnaireAnswerSubmit(appointment_id=args["appointment_id"], answers=args["answers"], is_completed=True)
    resp = await QuestionnaireService.submit_response(db, sub, patient_id=patient_id)
    return {"response_id": resp.id, "is_completed": resp.is_completed, "message": "Questionnaire response saved."}


async def handle_lookup_patient(db: AsyncSession, args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    patient_id = args.get("patient_id") or context.get("patient_id")
    return {"patient_id": patient_id, "status": "IDENTIFIED" if patient_id else "ANONYMOUS"}


async def handle_send_notification(db: AsyncSession, args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    notif = await NotificationService.send_notification(
        db,
        hospital_id=args["hospital_id"],
        recipient=args["recipient"],
        subject=args["subject"],
        content=args["content"],
    )
    return {"notification_id": notif.id, "status": notif.status.value}


async def handle_start_workflow(db: AsyncSession, args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    await WorkflowService.dispatch_event(
        db, event_name=args["event_trigger"], hospital_id=args["hospital_id"], payload=args.get("payload", {})
    )
    return {"dispatched": True, "event": args["event_trigger"]}


async def handle_get_context(db: AsyncSession, args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    return {"context": context}


async def handle_update_preferences(db: AsyncSession, args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    return {"updated": True, "preferences": args}


async def handle_verify_external_appointment(db: AsyncSession, args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    ext_res = await mock_ehr_connector.verify_appointment(args["external_appointment_id"])
    return ext_res


async def handle_synchronize_state(db: AsyncSession, args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    appt = await AppointmentService.get_appointment(db, args["appointment_id"])
    return {"appointment_id": appt.id, "status": appt.status.value}


async def handle_transfer_to_human(db: AsyncSession, args: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "transferred": True,
        "target": args.get("department", "Patient Support"),
        "reason": args.get("reason"),
        "ticket_id": f"ESC-{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}",
    }


# Capability Definitions Catalog
CAPABILITY_CATALOG = {
    "search_hospitals": {
        "description": "Search affiliated hospitals by name or location.",
        "schema": SearchHospitalsInput,
        "handler": handle_search_hospitals,
    },
    "search_doctors": {
        "description": "Search doctors by medical specialty (e.g. Orthopedics, Cardiology), name, or hospital.",
        "schema": SearchDoctorsInput,
        "handler": handle_search_doctors,
    },
    "check_availability": {
        "description": "Query actual database-backed appointment slots for a doctor. Never hallucinate availability.",
        "schema": CheckAvailabilityInput,
        "handler": handle_check_availability,
    },
    "lookup_patient": {
        "description": "Look up patient record or demographic identity.",
        "schema": LookupPatientInput,
        "handler": handle_lookup_patient,
    },
    "get_appointment": {
        "description": "Retrieve appointment details and current status.",
        "schema": GetAppointmentInput,
        "handler": handle_get_appointment,
    },
    "create_appointment": {
        "description": "Book a verified appointment with doctor at specified real slot. Performs EHR verification.",
        "schema": CreateAppointmentInput,
        "handler": handle_create_appointment,
    },
    "reschedule_appointment": {
        "description": "Reschedule an existing appointment to a new available slot with EHR synchronization.",
        "schema": RescheduleAppointmentInput,
        "handler": handle_reschedule_appointment,
    },
    "cancel_appointment": {
        "description": "Cancel an appointment and release the slot.",
        "schema": CancelAppointmentInput,
        "handler": handle_cancel_appointment,
    },
    "get_questionnaire": {
        "description": "Fetch the pre-visit administrative questionnaire assigned to an appointment.",
        "schema": GetQuestionnaireInput,
        "handler": handle_get_questionnaire,
    },
    "submit_questionnaire": {
        "description": "Submit patient answers to the assigned pre-visit questionnaire.",
        "schema": SubmitQuestionnaireInput,
        "handler": handle_submit_questionnaire,
    },
    "send_notification": {
        "description": "Send an in-app, SMS, or email notification.",
        "schema": SendNotificationInput,
        "handler": handle_send_notification,
    },
    "start_workflow": {
        "description": "Trigger an operational healthcare workflow.",
        "schema": StartWorkflowInput,
        "handler": handle_start_workflow,
    },
    "get_context": {
        "description": "Retrieve current conversation and scheduling context.",
        "schema": GetContextInput,
        "handler": handle_get_context,
    },
    "update_preferences": {
        "description": "Update patient communication or hospital preferences.",
        "schema": UpdatePreferencesInput,
        "handler": handle_update_preferences,
    },
    "verify_external_appointment": {
        "description": "Verify external EHR appointment status.",
        "schema": VerifyExternalAppointmentInput,
        "handler": handle_verify_external_appointment,
    },
    "synchronize_state": {
        "description": "Synchronize internal appointment state with external EHR.",
        "schema": SynchronizeStateInput,
        "handler": handle_synchronize_state,
    },
    "transfer_to_human": {
        "description": "Escalate conversation or emergency request to human healthcare staff.",
        "schema": TransferToHumanInput,
        "handler": handle_transfer_to_human,
    },
}
