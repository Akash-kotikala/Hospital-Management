# REST API & OpenAPI Documentation

[← Back to Repository README](../README.md)

---

## 1. Overview & Interactive Documentation

The FastAPI backend provides interactive OpenAPI documentation out-of-the-box:

- **Swagger UI**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **ReDoc UI**: [http://localhost:8000/redoc](http://localhost:8000/redoc)
- **Web App Dashboard**: [http://localhost:8000/](http://localhost:8000/)

---

## 2. Standard Request Headers

| Header | Description | Required |
| :--- | :--- | :--- |
| `Authorization` | `Bearer <JWT_ACCESS_TOKEN>` | Yes (for protected endpoints) |
| `X-Correlation-ID` | Distributed correlation tracking identifier | Optional (auto-generated UUID if omitted) |
| `X-Operation-ID` | Atomic business operation identifier | Optional (auto-generated UUID if omitted) |

---

## 3. Standardized Error Response Format

All API errors strictly conform to the PRD Section 27 error schema:

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
- `POST /api/auth/login`: Authenticate credentials and receive JWT token
- `GET /api/auth/me`: Retrieve current profile, permissions, and assigned hospital

### Hospitals & Multi-Tenancy (`/api/hospitals`)
- `POST /api/hospitals`: Register new hospital tenant (`DRAFT`)
- `GET /api/hospitals`: List hospitals (filter by status)
- `POST /api/hospitals/{id}/submit`: Submit onboarding application
- `POST /api/hospitals/{id}/approve`: Platform Admin approval
- `POST /api/hospitals/{id}/reject`: Platform Admin rejection

### Doctors & Real Availability (`/api/doctors`)
- `POST /api/doctors`: Create doctor under approved hospital
- `GET /api/doctors`: Discover doctors by medical specialty or hospital
- `POST /api/doctors/{id}/availability`: Configure weekly working hours
- `POST /api/doctors/{id}/blocked-slots`: Block leaves or emergency periods
- `GET /api/doctors/{id}/slots`: Query real database-backed bookable slots

### Appointments & Two-Phase Booking (`/api/appointments`)
- `POST /api/appointments`: Execute booking with two-phase EHR verification
- `GET /api/appointments`: List appointments (tenant & role scoped)
- `GET /api/appointments/{id}`: View appointment lifecycle and history
- `POST /api/appointments/{id}/reschedule`: Reschedule with EHR update
- `POST /api/appointments/{id}/cancel`: Cancel booking and release slot

### Pre-Visit Questionnaires (`/api/questionnaires`)
- `POST /api/questionnaires`: Configure approved intake questions
- `POST /api/questionnaires/{id}/responses`: Submit patient answers
- `POST /api/questionnaires/responses/{id}/review`: Doctor review and notes

### AI Agent & Voice Intake (`/api/ai`)
- `POST /api/ai/chat`: Interactive chat with AI Agent & capability execution
- `POST /api/ai/voice/session`: Initialize voice session
- `POST /api/ai/voice/process`: Process audio transcript

### Integrations & Demo Controls (`/api/integrations` & `/mock-ehr`)
- `POST /api/integrations/failure-mode`: Demo control to arm Mock EHR timeout
- `GET /api/integrations/reconciliation`: View investigated reconciliation records
- `POST /api/integrations/reconciliation/{id}/resolve`: Resolve reconciliation record
