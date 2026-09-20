# AI Administrative Patient Access Agent & Controlled Capabilities

## 1. Safety Boundaries & Operational Scope

The AI assistant operates strictly as an **administrative healthcare access coordinator**. It adheres to the following non-negotiable safety guardrails:

> [!CAUTION]
> **Strict Clinical Guardrails:**
> - The AI **NEVER** diagnoses medical conditions.
> - The AI **NEVER** prescribes medications or suggests dosages.
> - The AI **NEVER** recommends clinical treatments or medication changes.
> - The AI **NEVER** performs independent clinical triage.
> - **Emergency Protocol**: If acute emergency symptoms are expressed (e.g. *"I have severe chest pain and shortness of breath"*), the assistant immediately halts routine scheduling, provides an urgent emergency alert to call 911 or visit the nearest ER, and marks the interaction as an emergency escalation.

---

## 2. Anti-Hallucination Availability Engine

The AI model is never allowed to fabricate appointment slots, hospital names, or doctor identities.
- Availability is determined dynamically via the `check_availability` capability, which queries the database-backed `SchedulingService`.
- No appointment is marked confirmed to the patient until external EHR verification succeeds.

---

## 3. Controlled Capability Architecture

The AI model **never has direct database or SQL access**. It executes exclusively through registered, strongly-typed capabilities:

```mermaid
sequenceDiagram
    autonumber
    actor Patient
    participant Agent as AI Agent (Gemini API)
    participant Cap as Capability Registry
    participant Sched as Scheduling Engine
    participant DB as PostgreSQL Database
    participant EHR as Mock EHR Connector

    Patient->>Agent: "I need an orthopedic doctor sometime this week."
    Agent->>Cap: invoke search_doctors(specialty="Orthopedics")
    Cap->>DB: query active doctors
    DB-->>Cap: returns [Dr. Marcus Rao]
    Cap-->>Agent: doctor details
    Agent->>Cap: invoke check_availability(doctor_id="...")
    Cap->>Sched: get_available_slots()
    Sched->>DB: filter blocked slots & booked appointments
    DB-->>Sched: real unbooked slots
    Sched-->>Cap: returns real slots [Option 1, Option 2, Option 3]
    Cap-->>Agent: slots
    Agent-->>Patient: "I found Dr. Marcus Rao. Here are available slots: Option 1..."
    Patient->>Agent: "Option 1 please."
    Agent->>Cap: invoke create_appointment(start_time="...")
    Cap->>EHR: create and verify record
    EHR-->>Cap: verified confirmation
    Cap-->>Agent: confirmed booking
    Agent-->>Patient: "Your appointment is verified and confirmed for Monday at 09:00 AM."
```

---

## 4. 17 Registered Capabilities Catalog

| Capability | Description | Input Schema |
| :--- | :--- | :--- |
| `search_hospitals` | Search approved hospitals by name/city | `SearchHospitalsInput` |
| `search_doctors` | Find doctors by medical specialty or name | `SearchDoctorsInput` |
| `check_availability` | Query genuine database slots for doctor | `CheckAvailabilityInput` |
| `lookup_patient` | Resolve patient identity and demographics | `LookupPatientInput` |
| `get_appointment` | Retrieve appointment status and history | `GetAppointmentInput` |
| `create_appointment` | Book appointment with two-phase EHR verification | `CreateAppointmentInput` |
| `reschedule_appointment`| Reschedule to a new real slot with EHR update | `RescheduleAppointmentInput`|
| `cancel_appointment` | Cancel booking and release slot | `CancelAppointmentInput` |
| `get_questionnaire` | Fetch pre-visit intake form assigned to appointment | `GetQuestionnaireInput` |
| `submit_questionnaire`| Submit structured patient intake answers | `SubmitQuestionnaireInput` |
| `send_notification` | Dispatch in-app, SMS, or email alert | `SendNotificationInput` |
| `start_workflow` | Trigger background operational workflow | `StartWorkflowInput` |
| `get_context` | Inspect conversation context state | `GetContextInput` |
| `update_preferences` | Update communication preferences | `UpdatePreferencesInput` |
| `verify_external_appointment`| Verify appointment existence in external EHR | `VerifyExternalAppointmentInput`|
| `synchronize_state` | Synchronize internal status with external EHR | `SynchronizeStateInput` |
| `transfer_to_human` | Escalate request or emergency to clinical staff | `TransferToHumanInput` |
