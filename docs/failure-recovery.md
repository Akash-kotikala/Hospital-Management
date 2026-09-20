# Failure Recovery & Reconciliation State Machine

[← Back to Repository README](../README.md)

---

## 1. Mandatory Failure Scenario

Healthcare scheduling platforms frequently encounter upstream network timeouts or dropped connections during external EHR writes. Blind retries risk duplicate appointments, double billing, and provider calendar corruption.

This platform implements the **Timeout Recovery State Machine**:

```mermaid
sequenceDiagram
    autonumber
    actor Patient
    participant Svc as Appointment Service
    participant Sched as Scheduling Engine
    participant EHR as Mock EHR
    participant Recon as Reconciliation Engine

    Patient->>Svc: Book Slot (Start: 09:00 AM)
    Svc->>Sched: Revalidate Slot Availability
    Sched-->>Svc: Slot is Valid & Free
    Svc->>Svc: Create Appointment in PENDING State
    Svc->>EHR: POST /appointments (with Idempotency Key)
    Note over Svc,EHR: Mock EHR Timeout Occurs!
    EHR--xSvc: 504 Gateway Timeout (UNKNOWN_OUTCOME)
    
    Svc->>Svc: Mark Status: SYNCHRONIZATION_PENDING
    Svc->>EHR: Query by Idempotency Key
    alt Appointment Exists in EHR?
        EHR-->>Svc: Found External Record (EHR-APPT-XXXX)
        Svc->>Svc: Synchronize State to CONFIRMED
        Svc->>Recon: Create ReconciliationRecord (Status: RESOLVED)
        Svc-->>Patient: "Appointment Verified and Confirmed."
    else Appointment Does NOT Exist?
        EHR-->>Svc: No Record Found
        Svc->>Svc: Mark Status: RECONCILIATION_REQUIRED
        Svc->>Recon: Create ReconciliationRecord (Status: ESCALATED)
        Svc-->>Patient: "Escalated to human staff to verify provider calendar."
    end
```

---

## 2. Preventing Duplicate Bookings

1. **Idempotency Keying**: Every booking attempt generates a unique UUID-based `idempotency_key`. The external query searches specifically by this key.
2. **Pessimistic Revalidation**: Before confirming any booking or retry, `revalidate_slot_availability()` verifies no active booking occupies the requested time window.
3. **Audit Records**: Every step logs an `AuditEvent` with `correlation_id` and `operation_id`.

---

## 3. Reconciliation Record Lifecycle

```mermaid
stateDiagram-v2
    [*] --> OPEN: Timeout / Sync Failure
    OPEN --> INVESTIGATING: System or Admin Queries State
    INVESTIGATING --> RESOLVED: External State Synchronized
    INVESTIGATING --> ESCALATED: Discrepancy Found / Human Review
    ESCALATED --> RESOLVED: Admin Manual Resolution
    RESOLVED --> [*]
```
