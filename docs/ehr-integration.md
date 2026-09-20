# Healthcare System & Mock EHR Integration

[← Back to Repository README](../README.md)

---

## 1. Connector Abstraction

To ensure modularity and readiness for enterprise EHR systems (Epic, Cerner, FHIR APIs), all EHR interactions are governed by the `HealthcareConnector` abstract interface.

```mermaid
classDiagram
    class HealthcareConnector {
        <<interface>>
        +lookup_patient(demographics)
        +get_providers(facility_id)
        +get_facilities()
        +create_appointment(payload)
        +get_appointment(external_id)
        +update_appointment(external_id, payload)
        +cancel_appointment(external_id, reason)
        +verify_appointment(external_id)
    }

    class MockEHRConnector {
        -_simulation_mode
        -_appointments
        -_patients
        +set_simulation_mode(mode, target_operation, countdown)
        +find_appointment_by_idempotency_key(idempotency_key)
    }

    HealthcareConnector <|.. MockEHRConnector
```

---

## 2. Two-Phase Verification Pattern

External systems must never be trusted based on an initial HTTP response alone. The platform enforces two-phase verification:

```mermaid
sequenceDiagram
    participant Platform as Appointment Service
    participant EHR as Mock EHR Connector

    Platform->>EHR: POST /appointments (Payload with Idempotency Key)
    EHR-->>Platform: 201 Created (external_id: "EHR-APPT-XXXX")
    Platform->>EHR: POST /appointments/EHR-APPT-XXXX/verify
    EHR-->>Platform: 200 OK (verified: true, status: "CONFIRMED")
    Platform->>Platform: Synchronize Internal State to CONFIRMED
```

---

## 3. Mock EHR Simulation Modes

The Mock EHR supports real-time fault injection for testing and resilience demonstrations:

| Mode | Behavior | Purpose |
| :--- | :--- | :--- |
| `NORMAL` | Standard immediate 201/200 confirmation | Happy path testing |
| `TIMEOUT` | Injects latency and raises `EHRTimeoutException` | Tests client timeout handling |
| `UNKNOWN_OUTCOME` | Saves record externally but drops client response | Demonstrates idempotency verification & safe recovery |
| `AUTH_ERROR` | Returns HTTP 401 Unauthorized | Validates authentication alert workflows |
| `SLOT_CONFLICT` | Returns HTTP 409 Conflict | Tests external provider conflict detection |
