# REST API & OpenAPI Documentation

## 1. Overview & Interactive Swagger UI

The FastAPI backend provides interactive OpenAPI documentation at:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`
- Direct UI: `http://localhost:8000/`

---

## 2. Standard Request Headers

| Header | Description | Default |
| :--- | :--- | :--- |
| `Authorization` | `Bearer <JWT_ACCESS_TOKEN>` | Required on protected endpoints |
| `X-Correlation-ID`| Distributed correlation tracking identifier | Auto-generated UUID if omitted |
| `X-Operation-ID`  | Atomic business operation identifier | Auto-generated UUID if omitted |

---

## 3. Standardized Error Response Format

All errors strictly conform to the PRD Section 27 schema:

```json
{
  "success": false,
  "error": {
    "code": "SLOT_NO_LONGER_AVAILABLE",
    "message": "The selected appointment slot is no longer available.",
    "correlation_id": "41c6f932-a567-4224-a213-9eb13981882d",
    "details": {}
  }
}
```

---

## 4. Key Endpoints Summary

### Authentication (`/api/auth`)
- `POST /api/auth/register`: Register new user (Patient, Hospital Admin, Doctor)
- `POST /api/auth/login`: Authenticate and obtain JWT token
- `GET /api/auth/me`: Retrieve current profile and role information

### Hospitals & Multi-Tenancy (`/api/hospitals`)
- `POST /api/hospitals`: Register new hospital tenant (`DRAFT`)
- `GET /api/hospitals`: List hospitals (filter by status)
- `POST /api/hospitals/{id}/submit`: Submit onboarding application
- `POST /api/hospitals/{id}/approve`: Platform Admin approval
- `POST /api/hospitals/{id}/reject`: Platform Admin rejection

### Doctors & Real Availability (`/api/doctors`)
- `POST /api/doctors`: Create doctor in approved hospital
- `GET /api/doctors`: Discover doctors by specialty or hospital
- `POST /api/doctors/{id}/availability`: Configure weekly working hours
- `POST /api/doctors/{id}/blocked-slots`: Block leaves or emergency periods
- `GET /api/doctors/{id}/slots`: Query real database-backed bookable slots

### Appointments & Two-Phase Booking (`/api/appointments`)
- `POST /api/appointments`: Execute booking with two-phase EHR verification
- `GET /api/appointments`: List appointments (tenant & role scoped)
- `GET /api/appointments/{id}`: View appointment lifecycle transition history
- `POST /api/appointments/{id}/reschedule`: Reschedule with EHR update
- `POST /api/appointments/{id}/cancel`: Cancel booking and release slot

### Pre-Visit Questionnaires (`/api/questionnaires`)
- `POST /api/questionnaires`: Configure approved intake questions
- `POST /api/questionnaires/{id}/responses`: Submit patient answers
- `POST /api/questionnaires/responses/{id}/review`: Doctor review and notes

### AI Agent & Voice Intake (`/api/ai`)
- `POST /api/ai/chat`: Interactive chat with AI Agent & capability execution
- `POST /api/ai/voice/session`: Initialize voice session
- `POST /api/ai/voice/process`: Audio transcript processing

### Integrations & Demo Controls (`/api/integrations` & `/mock-ehr`)
- `POST /api/integrations/failure-mode`: Demo control to arm Mock EHR timeout
- `GET /api/integrations/reconciliation`: View investigated reconciliation records
- `POST /api/integrations/reconciliation/{id}/resolve`: Resolve reconciliation record
