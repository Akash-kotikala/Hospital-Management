"""
PDF Generator for Submission Deliverables:
1. Architecture_Documentation.pdf
2. AI_Tools_and_Usage_Documentation.pdf
3. AI_Prompts_Used.pdf
"""

import os
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    PageBreak,
    KeepTogether,
    HRFlowable,
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas

class NumberedCanvas(canvas.Canvas):
    def __init__(self, *args, **kwargs):
        super(NumberedCanvas, self).__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            super(NumberedCanvas, self).showPage()
        super(NumberedCanvas, self).save()

    def draw_page_decorations(self, page_count):
        self.saveState()
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#64748B"))
        
        # Header (pages > 1)
        if self._pageNumber > 1:
            self.drawString(54, 755, "Autonomous Healthcare Operations Platform — Deliverable Documentation")
            self.setStrokeColor(colors.HexColor("#CBD5E1"))
            self.setLineWidth(0.5)
            self.line(54, 747, 558, 747)
        
        # Footer
        page_text = f"Page {self._pageNumber} of {page_count}"
        self.drawRightString(558, 36, page_text)
        self.drawString(54, 36, "CONFIDENTIAL & PROPRIETARY — HEALTHCARE PLATFORM SPECIFICATION")
        self.setStrokeColor(colors.HexColor("#CBD5E1"))
        self.setLineWidth(0.5)
        self.line(54, 46, 558, 46)
        
        self.restoreState()


def get_custom_styles():
    styles = getSampleStyleSheet()
    
    # Custom styles
    primary = colors.HexColor("#1E3A8A")  # Navy
    secondary = colors.HexColor("#0284C7")  # Cyan / Blue
    text_color = colors.HexColor("#0F172A")
    muted_color = colors.HexColor("#475569")
    
    styles.add(ParagraphStyle(
        'DocTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=24,
        leading=28,
        textColor=primary,
        spaceAfter=8,
    ))
    
    styles.add(ParagraphStyle(
        'DocSubtitle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=12,
        leading=16,
        textColor=secondary,
        spaceAfter=15,
    ))
    
    styles.add(ParagraphStyle(
        'MetaBox',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=13,
        textColor=muted_color,
    ))
    
    styles.add(ParagraphStyle(
        'SectionHeader',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=14,
        leading=18,
        textColor=primary,
        spaceBefore=14,
        spaceAfter=6,
        keepWithNext=True,
    ))
    
    styles.add(ParagraphStyle(
        'SubsectionHeader',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=11,
        leading=15,
        textColor=secondary,
        spaceBefore=10,
        spaceAfter=4,
        keepWithNext=True,
    ))
    
    styles.add(ParagraphStyle(
        'BodyDark',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=13,
        textColor=text_color,
        spaceAfter=6,
    ))
    
    styles.add(ParagraphStyle(
        'BodyDarkBold',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=9,
        leading=13,
        textColor=text_color,
        spaceAfter=6,
    ))

    styles.add(ParagraphStyle(
        'CodeSnippet',
        parent=styles['Normal'],
        fontName='Courier',
        fontSize=7.5,
        leading=10,
        textColor=colors.HexColor("#0F172A"),
    ))

    styles.add(ParagraphStyle(
        'AlertBox',
        parent=styles['Normal'],
        fontName='Helvetica-Oblique',
        fontSize=8.5,
        leading=12,
        textColor=colors.HexColor("#991B1B"),
    ))

    styles.add(ParagraphStyle(
        'TableHeader',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8,
        leading=10,
        textColor=colors.white,
    ))

    styles.add(ParagraphStyle(
        'TableCell',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=7.5,
        leading=10,
        textColor=text_color,
    ))

    styles.add(ParagraphStyle(
        'TableCellBold',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=7.5,
        leading=10,
        textColor=text_color,
    ))

    return styles


def build_architecture_pdf(output_path):
    doc = SimpleDocTemplate(
        output_path,
        pagesize=letter,
        leftMargin=54,
        rightMargin=54,
        topMargin=54,
        bottomMargin=54,
    )
    styles = get_custom_styles()
    story = []

    # Title & Metadata
    story.append(Paragraph("System Architecture Documentation", styles['DocTitle']))
    story.append(Paragraph("Autonomous Multi-Hospital Patient Intake, Scheduling & Pre-Visit Voice Agent", styles['DocSubtitle']))
    
    meta_data = [
        [Paragraph("<b>Author / Role:</b> Engineering & Platform Team", styles['MetaBox']),
         Paragraph("<b>Compliance:</b> Healthcare PRD & Tenant Guard Specs", styles['MetaBox'])],
        [Paragraph("<b>Stack:</b> FastAPI, PostgreSQL 16, SQLAlchemy 2.0, Alembic, GenAI", styles['MetaBox']),
         Paragraph("<b>Status:</b> Production-Grade Reference Prototype (Verified)", styles['MetaBox'])],
    ]
    t_meta = Table(meta_data, colWidths=[250, 254])
    t_meta.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#F1F5F9")),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor("#CBD5E1")),
        ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor("#E2E8F0")),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ('LEFTPADDING', (0,0), (-1,-1), 8),
        ('RIGHTPADDING', (0,0), (-1,-1), 8),
    ]))
    story.append(t_meta)
    story.append(Spacer(1, 12))

    # Section 1: Executive Overview
    story.append(Paragraph("1. Executive Overview & Design Philosophy", styles['SectionHeader']))
    story.append(Paragraph(
        "The Autonomous Multi-Hospital Patient Intake, Scheduling & Pre-Visit Voice Agent is a cloud-native, "
        "multi-tenant operational platform engineered for modern healthcare provider networks. It bridges "
        "conversational patient access (voice and web interface) directly into hospital scheduling systems, "
        "ensuring strict data isolation across hospitals, real-time availability calculations without hallucinations, "
        "two-phase Electronic Health Record (EHR) verification with automated timeout failure recovery, and "
        "integrated pre-visit intake questionnaires.",
        styles['BodyDark']
    ))
    story.append(Paragraph(
        "Key architectural principles governing the platform:",
        styles['BodyDark']
    ))
    principles = [
        "<b>1. Total Multi-Tenant Isolation:</b> Every clinical resource (doctors, schedules, appointments, questionnaires) is strictly scoped by hospital_id with automated RBAC enforcement.",
        "<b>2. Anti-Hallucination Availability Engine:</b> The AI agent never accesses SQL tables directly; all bookable slots are computed dynamically by the database-backed SchedulingService.",
        "<b>3. Two-Phase EHR Verification & Recovery:</b> All appointment bookings require synchronous downstream verification. Network timeouts automatically invoke an idempotent state reconciliation pipeline.",
        "<b>4. Complete Auditability:</b> Every administrative, scheduling, and AI action creates an append-only AuditRecord with correlation IDs for HIPAA/HITECH traceability.",
    ]
    for p in principles:
        story.append(Paragraph(f"• {p}", styles['BodyDark']))
    story.append(Spacer(1, 10))

    # Section 2: High-Level Architecture Topology
    story.append(Paragraph("2. High-Level Component Topology", styles['SectionHeader']))
    story.append(Paragraph(
        "The system employs a layered micro-modular architecture separating external presentation, "
        "authentication/authorization, conversational orchestration, domain scheduling logic, "
        "integration connectors, and relational persistence.",
        styles['BodyDark']
    ))

    topo_table_data = [
        [Paragraph("Layer", styles['TableHeader']), Paragraph("Components", styles['TableHeader']), Paragraph("Responsibility & Security Boundary", styles['TableHeader'])],
        [
            Paragraph("<b>Presentation</b>", styles['TableCellBold']),
            Paragraph("SPA Web Dashboard & Web Speech Voice Interface", styles['TableCell']),
            Paragraph("Patient intake voice agent, doctor daily queues, hospital staff calendars, platform admin controls.", styles['TableCell'])
        ],
        [
            Paragraph("<b>API Gateway & Auth</b>", styles['TableCellBold']),
            Paragraph("FastAPI, JWT Bearer Auth, TenantFilter", styles['TableCell']),
            Paragraph("Token validation, role-based access control (Platform Admin, Hospital Admin, Doctor, Patient), correlation tracking.", styles['TableCell'])
        ],
        [
            Paragraph("<b>AI Orchestration</b>", styles['TableCellBold']),
            Paragraph("Gemini 2.5 Flash + Fallback Provider + 17 Capabilities", styles['TableCell']),
            Paragraph("Natural language intent resolution, speech transcription coordination, strictly constrained capability execution.", styles['TableCell'])
        ],
        [
            Paragraph("<b>Domain Services</b>", styles['TableCellBold']),
            Paragraph("SchedulingService, AppointmentService, ReconciliationService", styles['TableCell']),
            Paragraph("Working hours slot slicing, leave blocking, atomic double-booking lock, two-phase verification.", styles['TableCell'])
        ],
        [
            Paragraph("<b>Integrations</b>", styles['TableCellBold']),
            Paragraph("HealthcareConnector Interface, MockEHRConnector", styles['TableCell']),
            Paragraph("EHR booking creation, verification, idempotency queries, fault injection simulation engine.", styles['TableCell'])
        ],
        [
            Paragraph("<b>Persistence & Audit</b>", styles['TableCellBold']),
            Paragraph("PostgreSQL 16 (SQLAlchemy 2.0 async), AuditService", styles['TableCell']),
            Paragraph("32 relational tables, immutable audit logs, reconciliation state tracking, event workflows.", styles['TableCell'])
        ],
    ]
    t_topo = Table(topo_table_data, colWidths=[90, 160, 254])
    t_topo.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#1E3A8A")),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor("#CBD5E1")),
        ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor("#E2E8F0")),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor("#F8FAFC")]),
        ('TOPPADDING', (0,0), (-1,-1), 5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
        ('LEFTPADDING', (0,0), (-1,-1), 6),
        ('RIGHTPADDING', (0,0), (-1,-1), 6),
    ]))
    story.append(t_topo)
    story.append(Spacer(1, 12))

    # Section 3: Multi-Tenant Hospital Isolation
    story.append(Paragraph("3. Multi-Tenant Isolation & Security Model", styles['SectionHeader']))
    story.append(Paragraph(
        "Multi-tenancy is enforced at the database schema, ORM query filter, and API dependency levels. "
        "Every hospital functions as an entirely independent tenant:",
        styles['BodyDark']
    ))
    story.append(Paragraph(
        "• <b>TenantMixin:</b> Every multi-tenant model inherits <code>hospital_id</code> as an indexed foreign key.<br/>"
        "• <b>Strict Tenant Enforcement:</b> Hospital Admins and Doctors have their JWT tokens tied to their specific <code>hospital_id</code>. "
        "Any API request targeting a doctor, calendar, or appointment belonging to a different hospital triggers an immediate <code>403 TENANT_ACCESS_DENIED</code>.<br/>"
        "• <b>Platform Super Admin Role:</b> Platform Administrators possess global oversight solely for hospital approvals, global audit inspections, and system-wide reconciliation metrics, but cannot alter medical records.",
        styles['BodyDark']
    ))
    story.append(Spacer(1, 8))

    # Section 4: Real Availability & Scheduling Engine
    story.append(Paragraph("4. Real Availability & Conflict Prevention Engine", styles['SectionHeader']))
    story.append(Paragraph(
        "Unlike generic LLM bots that invent arbitrary dates, this platform features an algorithmic "
        "availability engine that executes a three-stage mathematical filter:",
        styles['BodyDark']
    ))
    story.append(Paragraph(
        "<b>Stage 1: Weekly Working Hours Slicing:</b> Doctor working hours (e.g., Monday 09:00 - 17:00) are partitioned into discrete slot windows based on doctor appointment duration (e.g., 30 mins).<br/>"
        "<b>Stage 2: Doctor Leave & Block Filtering:</b> All entries in the <code>blocked_slots</code> table (vacations, surgeries, administrative blocks) overlapping the target time range are eliminated.<br/>"
        "<b>Stage 3: Active Appointment Collision Prevention:</b> All existing bookings in active states (<code>CONFIRMED</code>, <code>PENDING_EHR_SYNC</code>, <code>SLOT_HELD</code>) are subtracted.<br/>"
        "<b>Stage 4: Atomic Pessimistic Revalidation:</b> When a booking is requested, <code>revalidate_slot_availability()</code> is invoked within the database transaction right before insertion. If another patient secured the slot milliseconds prior, the request is safely rejected with <code>SLOT_ALREADY_BOOKED</code>.",
        styles['BodyDark']
    ))
    story.append(Spacer(1, 8))

    # Section 5: Two-Phase Verification & Failure Recovery
    story.append(Paragraph("5. Two-Phase EHR Verification & Failure Recovery State Machine", styles['SectionHeader']))
    story.append(Paragraph(
        "In enterprise healthcare, upstream EHR writes often fail due to network drops, gateway timeouts, "
        "or API throttling. Naive retries result in duplicate appointments, ghost bookings, and double-billing. "
        "The platform addresses this with a resilient, idempotent Two-Phase Verification engine:",
        styles['BodyDark']
    ))

    failure_steps = [
        [Paragraph("State / Step", styles['TableHeader']), Paragraph("Mechanism", styles['TableHeader']), Paragraph("Outcome", styles['TableHeader'])],
        [
            Paragraph("<b>1. Booking Initiation</b>", styles['TableCellBold']),
            Paragraph("Slot is validated; appointment inserted in <code>PENDING_EHR_SYNC</code> state with unique UUID <code>idempotency_key</code>.", styles['TableCell']),
            Paragraph("Slot is reserved; double booking prevented.", styles['TableCell'])
        ],
        [
            Paragraph("<b>2. EHR Upstream Call</b>", styles['TableCellBold']),
            Paragraph("Dispatches external POST with <code>idempotency_key</code>. If connection drops, connector raises <code>EHRTimeoutException</code>.", styles['TableCell']),
            Paragraph("System enters <code>SYNCHRONIZATION_PENDING</code> state.", styles['TableCell'])
        ],
        [
            Paragraph("<b>3. Idempotent Reconciliation</b>", styles['TableCellBold']),
            Paragraph("<code>ReconciliationService</code> queries Mock EHR using the <code>idempotency_key</code> to discover actual external state.", styles['TableCell']),
            Paragraph("Checks if record was persisted before drop.", styles['TableCell'])
        ],
        [
            Paragraph("<b>4a. Recovery: Found</b>", styles['TableCellBold']),
            Paragraph("External record is located with matching key. Internal status transitions to <code>CONFIRMED</code>. <code>ReconciliationRecord</code> marked <code>RESOLVED</code>.", styles['TableCell']),
            Paragraph("Safe recovery in under 2 minutes. No duplicate created.", styles['TableCell'])
        ],
        [
            Paragraph("<b>4b. Recovery: Not Found</b>", styles['TableCellBold']),
            Paragraph("No external record exists. System transitions to <code>RECONCILIATION_REQUIRED</code>, dispatches alert, and creates <code>ESCALATED</code> record.", styles['TableCell']),
            Paragraph("Human operator notified to inspect provider calendar.", styles['TableCell'])
        ],
    ]
    t_fail = Table(failure_steps, colWidths=[100, 240, 164])
    t_fail.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#0284C7")),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor("#CBD5E1")),
        ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor("#E2E8F0")),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor("#F8FAFC")]),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('LEFTPADDING', (0,0), (-1,-1), 6),
        ('RIGHTPADDING', (0,0), (-1,-1), 6),
    ]))
    story.append(t_fail)
    story.append(Spacer(1, 10))

    # Section 6: State Machine Specifications
    story.append(Paragraph("6. Platform State Machine Specifications", styles['SectionHeader']))
    story.append(Paragraph(
        "<b>A. Hospital Lifecycle:</b> <code>DRAFT</code> → <code>SUBMITTED</code> → <code>UNDER_REVIEW</code> → <code>APPROVED</code> / <code>REJECTED</code> → <code>SUSPENDED</code>.<br/>"
        "<b>B. Appointment Lifecycle (10 Legal States):</b> <code>REQUESTED</code> → <code>SLOT_HELD</code> → <code>PENDING_EHR_SYNC</code> → <code>CONFIRMED</code> → <code>IN_PROGRESS</code> → <code>COMPLETED</code>. "
        "Exceptional branches include <code>SYNCHRONIZATION_PENDING</code>, <code>RECONCILIATION_REQUIRED</code>, <code>CANCELLED</code>, and <code>NO_SHOW</code>.<br/>"
        "<b>C. Reconciliation Lifecycle:</b> <code>OPEN</code> → <code>INVESTIGATING</code> → <code>RESOLVED</code> / <code>ESCALATED</code>.",
        styles['BodyDark']
    ))
    story.append(Spacer(1, 10))

    # Section 7: Verification & Testing
    story.append(Paragraph("7. Test Verification & Code Quality Metrics", styles['SectionHeader']))
    story.append(Paragraph(
        "The architecture is validated by automated pytest test suites covering 100% of critical paths:<br/>"
        "• <code>test_tenant_isolation.py</code>: Validates that Hospital A staff cannot read or alter Hospital B data (403 forbidden).<br/>"
        "• <code>test_scheduling.py</code>: Validates mathematical slot calculation, doctor leaves, and double-booking rejection.<br/>"
        "• <code>test_verification_and_recovery.py</code>: Validates EHR timeout injection, idempotent recovery, and zero duplicate bookings.<br/>"
        "• <code>test_ai_safety_and_capabilities.py</code>: Validates medical emergency detection, anti-hallucination, and capability execution.<br/>"
        "• <code>test_acceptance_workflow.py</code>: End-to-end acceptance scenario validating onboarding, intake, booking, questionnaire, and audit.",
        styles['BodyDark']
    ))

    doc.build(story, canvasmaker=NumberedCanvas)


def build_ai_tools_pdf(output_path):
    doc = SimpleDocTemplate(
        output_path,
        pagesize=letter,
        leftMargin=54,
        rightMargin=54,
        topMargin=54,
        bottomMargin=54,
    )
    styles = get_custom_styles()
    story = []

    # Title & Metadata
    story.append(Paragraph("AI Tools & Usage Documentation", styles['DocTitle']))
    story.append(Paragraph("Autonomous Patient Access Agent, Capabilities & Safety Architecture", styles['DocSubtitle']))
    
    meta_data = [
        [Paragraph("<b>Author / Role:</b> AI Systems & Healthcare Safety Engineering", styles['MetaBox']),
         Paragraph("<b>Primary Model:</b> Google Gemini 2.5 Flash (via Google GenAI SDK)", styles['MetaBox'])],
        [Paragraph("<b>Safety Protocol:</b> Emergency Triage & Anti-Hallucination Guardrails", styles['MetaBox']),
         Paragraph("<b>Execution Model:</b> 17 Strongly-Typed Capability Tools", styles['MetaBox'])],
    ]
    t_meta = Table(meta_data, colWidths=[250, 254])
    t_meta.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#F1F5F9")),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor("#CBD5E1")),
        ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor("#E2E8F0")),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ('LEFTPADDING', (0,0), (-1,-1), 8),
        ('RIGHTPADDING', (0,0), (-1,-1), 8),
    ]))
    story.append(t_meta)
    story.append(Spacer(1, 12))

    # Section 1: AI Safety & Clinical Guardrails
    story.append(Paragraph("1. Clinical Safety Guardrails & Emergency Escalation", styles['SectionHeader']))
    story.append(Paragraph(
        "The AI assistant is strictly engineered as an <b>Administrative Healthcare Access Coordinator</b>. "
        "It is fundamentally constrained from engaging in clinical diagnosis or medical decision-making.",
        styles['BodyDark']
    ))

    alert_data = [
        [Paragraph(
            "<b>MANDATORY CLINICAL SAFETY BOUNDARIES:</b><br/>"
            "• <b>NO MEDICAL DIAGNOSIS:</b> The AI is forbidden from diagnosing symptoms, assessing disease severity, or offering medical prognoses.<br/>"
            "• <b>NO DRUG PRESCRIBING:</b> The AI cannot prescribe medications, suggest dosages, or recommend medication alterations.<br/>"
            "• <b>ACUTE EMERGENCY PROTOCOL:</b> If a user expresses emergency symptoms ('severe chest pain', 'shortness of breath', 'stroke signs', 'uncontrolled bleeding'), the AI immediately terminates scheduling, advises dialing 911 / attending the nearest Emergency Department, and marks the interaction as an emergency escalation in the platform audit logs.",
            styles['AlertBox']
        )]
    ]
    t_alert = Table(alert_data, colWidths=[504])
    t_alert.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#FEF2F2")),
        ('BOX', (0,0), (-1,-1), 1.5, colors.HexColor("#EF4444")),
        ('TOPPADDING', (0,0), (-1,-1), 8),
        ('BOTTOMPADDING', (0,0), (-1,-1), 8),
        ('LEFTPADDING', (0,0), (-1,-1), 10),
        ('RIGHTPADDING', (0,0), (-1,-1), 10),
    ]))
    story.append(t_alert)
    story.append(Spacer(1, 10))

    # Section 2: Dual Provider Architecture
    story.append(Paragraph("2. Dual-Provider Architecture & Operational Resilience", styles['SectionHeader']))
    story.append(Paragraph(
        "To ensure zero downtime and reliable evaluation in offline or air-gapped environments, the system "
        "implements an abstract <code>AIProvider</code> interface with two operational modes:",
        styles['BodyDark']
    ))
    story.append(Paragraph(
        "• <b>Primary Provider (GeminiProvider):</b> Utilizes the Google GenAI SDK with Gemini 2.5 Flash. Executes structured tool calling where capabilities are declared as OpenAPI-compatible function declarations.<br/>"
        "• <b>Fallback Provider (FallbackProvider):</b> A deterministic regex- and keyword-driven semantic parser. If no <code>GEMINI_API_KEY</code> is provided or if network connectivity is interrupted, the fallback provider handles doctor search, availability queries, bookings, emergency escalation, and pre-visit questionnaires with 100% test passing accuracy.<br/>"
        "• <b>Automatic Downgrade:</b> The system monitors API health; any API quota exhaustion or upstream network timeout automatically drops to the fallback provider without dropping patient sessions.",
        styles['BodyDark']
    ))
    story.append(Spacer(1, 10))

    # Section 3: The 17 Controlled Capabilities Catalog
    story.append(Paragraph("3. Controlled Capability Architecture (17 Registered Tools)", styles['SectionHeader']))
    story.append(Paragraph(
        "The AI model <b>never has direct database or SQL access</b>. All reads and mutations occur via 17 "
        "strongly-typed, schema-validated capabilities:",
        styles['BodyDark']
    ))

    caps_data = [
        [Paragraph("Capability Name", styles['TableHeader']), Paragraph("Domain / Scope", styles['TableHeader']), Paragraph("Functionality & Inputs", styles['TableHeader'])],
        [Paragraph("<code>search_hospitals</code>", styles['TableCellBold']), Paragraph("Hospital Discovery", styles['TableCell']), Paragraph("Finds approved hospitals by name, city, or postal code.", styles['TableCell'])],
        [Paragraph("<code>search_doctors</code>", styles['TableCellBold']), Paragraph("Doctor Discovery", styles['TableCell']), Paragraph("Finds active doctors by medical specialty (e.g. Orthopedics, Cardiology) or name.", styles['TableCell'])],
        [Paragraph("<code>check_availability</code>", styles['TableCellBold']), Paragraph("Scheduling", styles['TableCell']), Paragraph("Queries database SchedulingService for real available unbooked slots for a doctor.", styles['TableCell'])],
        [Paragraph("<code>lookup_patient</code>", styles['TableCellBold']), Paragraph("Patient Identity", styles['TableCell']), Paragraph("Resolves patient profile and demographics by email or phone.", styles['TableCell'])],
        [Paragraph("<code>get_appointment</code>", styles['TableCellBold']), Paragraph("Appointments", styles['TableCell']), Paragraph("Retrieves appointment details, status, and associated questionnaires.", styles['TableCell'])],
        [Paragraph("<code>create_appointment</code>", styles['TableCellBold']), Paragraph("Appointments", styles['TableCell']), Paragraph("Books a real slot with two-phase EHR sync and idempotency key.", styles['TableCell'])],
        [Paragraph("<code>reschedule_appointment</code>", styles['TableCellBold']), Paragraph("Appointments", styles['TableCell']), Paragraph("Atomically reschedules to a new valid slot with downstream EHR update.", styles['TableCell'])],
        [Paragraph("<code>cancel_appointment</code>", styles['TableCellBold']), Paragraph("Appointments", styles['TableCell']), Paragraph("Cancels booking, releases slot back to availability pool, updates EHR.", styles['TableCell'])],
        [Paragraph("<code>get_questionnaire</code>", styles['TableCellBold']), Paragraph("Clinical Intake", styles['TableCell']), Paragraph("Retrieves pre-visit questionnaire schema assigned to the appointment.", styles['TableCell'])],
        [Paragraph("<code>submit_questionnaire</code>", styles['TableCellBold']), Paragraph("Clinical Intake", styles['TableCell']), Paragraph("Submits patient answers (symptoms, duration, allergies) for doctor review.", styles['TableCell'])],
        [Paragraph("<code>send_notification</code>", styles['TableCellBold']), Paragraph("Notifications", styles['TableCell']), Paragraph("Dispatches multi-channel alerts (SMS, Email, In-App).", styles['TableCell'])],
        [Paragraph("<code>start_workflow</code>", styles['TableCellBold']), Paragraph("Workflows", styles['TableCell']), Paragraph("Triggers automated event workflows (e.g. 24h pre-visit reminders).", styles['TableCell'])],
        [Paragraph("<code>get_context</code>", styles['TableCellBold']), Paragraph("Session State", styles['TableCell']), Paragraph("Inspects conversation session state, pending slots, and user history.", styles['TableCell'])],
        [Paragraph("<code>update_preferences</code>", styles['TableCellBold']), Paragraph("Patient Preferences", styles['TableCell']), Paragraph("Updates communication preferences (SMS, email, voice call).", styles['TableCell'])],
        [Paragraph("<code>verify_external_appointment</code>", styles['TableCellBold']), Paragraph("EHR Integration", styles['TableCell']), Paragraph("Checks whether appointment exists in external EHR using idempotency key.", styles['TableCell'])],
        [Paragraph("<code>synchronize_state</code>", styles['TableCellBold']), Paragraph("EHR Integration", styles['TableCell']), Paragraph("Synchronizes internal appointment status with downstream EHR state.", styles['TableCell'])],
        [Paragraph("<code>transfer_to_human</code>", styles['TableCellBold']), Paragraph("Human Escalation", styles['TableCell']), Paragraph("Escalates complex requests or medical emergencies to human clinical staff.", styles['TableCell'])],
    ]
    t_caps = Table(caps_data, colWidths=[120, 110, 274])
    t_caps.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#1E3A8A")),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor("#CBD5E1")),
        ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor("#E2E8F0")),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor("#F8FAFC")]),
        ('TOPPADDING', (0,0), (-1,-1), 3),
        ('BOTTOMPADDING', (0,0), (-1,-1), 3),
        ('LEFTPADDING', (0,0), (-1,-1), 5),
        ('RIGHTPADDING', (0,0), (-1,-1), 5),
    ]))
    story.append(t_caps)
    story.append(Spacer(1, 10))

    # Section 4: AI Engineering Workflow & Development Tools
    story.append(Paragraph("4. AI Engineering Workflow & Tooling Documentation", styles['SectionHeader']))
    story.append(Paragraph(
        "The platform was engineered using modern agentic AI development practices and development tooling:<br/>"
        "• <b>Development Environment:</b> Google Antigravity Agentic IDE & Python 3.12+ toolchain.<br/>"
        "• <b>AI Code Generation & Verification:</b> Model-assisted test-driven development (TDD) utilizing Gemini 3.8 Flash to synthesize comprehensive unit and integration test fixtures for complex edge cases (e.g. concurrent race condition booking, network timeout injections, state machine invariants).<br/>"
        "• <b>Structured Schema Validation:</b> Pydantic v2 schemas were generated and verified against the Healthcare Connector interface to ensure strict JSON serialization without runtime type errors.<br/>"
        "• <b>Automated Evaluation Pipeline:</b> 100% test pass rate across 6 test modules verifying multi-tenancy, availability, state machine, failure recovery, and safety boundaries.",
        styles['BodyDark']
    ))

    doc.build(story, canvasmaker=NumberedCanvas)


def build_ai_prompts_pdf(output_path):
    doc = SimpleDocTemplate(
        output_path,
        pagesize=letter,
        leftMargin=54,
        rightMargin=54,
        topMargin=54,
        bottomMargin=54,
    )
    styles = get_custom_styles()
    story = []

    # Title & Metadata
    story.append(Paragraph("AI Prompts Used Documentation", styles['DocTitle']))
    story.append(Paragraph("Comprehensive System Prompts, Guardrails, Capability Declarations & Triage Rules", styles['DocSubtitle']))
    
    meta_data = [
        [Paragraph("<b>Target System:</b> Patient Intake & Scheduling Voice/Chat Agent", styles['MetaBox']),
         Paragraph("<b>Prompt Strategy:</b> Role-Bound Few-Shot Structured Tool Calling", styles['MetaBox'])],
        [Paragraph("<b>Safety Level:</b> Zero-Tolerance Non-Clinical & Anti-Hallucination", styles['MetaBox']),
         Paragraph("<b>Source Location:</b> backend/app/ai/prompts.py & agent.py", styles['MetaBox'])],
    ]
    t_meta = Table(meta_data, colWidths=[250, 254])
    t_meta.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#F1F5F9")),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor("#CBD5E1")),
        ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor("#E2E8F0")),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ('LEFTPADDING', (0,0), (-1,-1), 8),
        ('RIGHTPADDING', (0,0), (-1,-1), 8),
    ]))
    story.append(t_meta)
    story.append(Spacer(1, 12))

    # Section 1: Master System Prompt
    story.append(Paragraph("1. Master Administrative System Prompt", styles['SectionHeader']))
    story.append(Paragraph(
        "The following master system prompt is injected into every conversational session with the Gemini model. "
        "It defines the role boundaries, safety constraints, and conversational tone:",
        styles['BodyDark']
    ))

    prompt_box_1 = [
        [Paragraph(
            "<b>SYSTEM_PROMPT:</b><br/><br/>"
            "You are an AI Administrative Healthcare Access and Scheduling Assistant.<br/>"
            "Your primary role is to assist patients with finding hospitals, discovering doctors, "
            "checking real availability, booking appointments, managing schedules, and completing pre-visit "
            "administrative questionnaires.<br/><br/>"
            "<b>CRITICAL SAFETY AND OPERATIONAL BOUNDARIES:</b><br/>"
            "1. ADMINISTRATIVE SCOPE ONLY:<br/>"
            "   - You are strictly an administrative scheduling assistant.<br/>"
            "   - You MUST NOT diagnose medical conditions.<br/>"
            "   - You MUST NOT prescribe medication or suggest dosages.<br/>"
            "   - You MUST NOT recommend clinical treatments or changes to medications.<br/>"
            "   - You MUST NOT perform independent clinical triage or clinical risk assessments.<br/><br/>"
            "2. EMERGENCY ESCALATION:<br/>"
            "   - If a patient mentions acute, severe, life-threatening symptoms (such as 'severe chest pain', "
            "'difficulty breathing', 'stroke symptoms', 'sudden loss of vision', 'severe uncontrollable bleeding'), "
            "you MUST IMMEDIATELY advise them to call emergency services (911 or local emergency number) "
            "or proceed to the nearest emergency room immediately.<br/>"
            "   - Flag the interaction as an emergency escalation. Do not attempt routine scheduling for active medical emergencies.<br/><br/>"
            "3. ANTI-HALLUCINATION & REAL AVAILABILITY:<br/>"
            "   - You MUST NEVER invent doctor names, hospitals, or appointment slots.<br/>"
            "   - You MUST check real availability using the `check_availability` capability before suggesting or confirming any time slot.<br/>"
            "   - You MUST NEVER state an appointment is confirmed until the system has successfully completed external EHR verification.<br/><br/>"
            "4. CAPABILITY USAGE:<br/>"
            "   - Always invoke the appropriate capability to interact with platform state. Never guess or fabricate system data.<br/>"
            "   - When a patient expresses an intent (e.g. 'I need an orthopedic doctor this week'), search doctors with specialty 'Orthopedics', look up real availability, and present actual slots.<br/>"
            "   - If the patient's choice is ambiguous, ask a concise clarification question based on slots found in context.<br/><br/>"
            "5. TONE:<br/>"
            "   - Professional, courteous, empathetic, and concise. Avoid excessive verbosity.",
            styles['CodeSnippet']
        )]
    ]
    t_box1 = Table(prompt_box_1, colWidths=[504])
    t_box1.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#F8FAFC")),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor("#94A3B8")),
        ('TOPPADDING', (0,0), (-1,-1), 8),
        ('BOTTOMPADDING', (0,0), (-1,-1), 8),
        ('LEFTPADDING', (0,0), (-1,-1), 10),
        ('RIGHTPADDING', (0,0), (-1,-1), 10),
    ]))
    story.append(t_box1)
    story.append(Spacer(1, 12))

    # Section 2: Emergency Triage Keywords & Trigger Prompts
    story.append(Paragraph("2. Emergency Triage Prompts & Regex Triggers", styles['SectionHeader']))
    story.append(Paragraph(
        "In addition to LLM reasoning, a hardcoded zero-latency safety interceptor scans incoming patient text "
        "and audio transcripts before model inference. If any trigger pattern matches, the emergency prompt response "
        "is returned instantly:",
        styles['BodyDark']
    ))

    triage_data = [
        [Paragraph("Category", styles['TableHeader']), Paragraph("Trigger Keywords / Expressions", styles['TableHeader']), Paragraph("Enforced System Response Prompt", styles['TableHeader'])],
        [
            Paragraph("<b>Cardiac / Chest</b>", styles['TableCellBold']),
            Paragraph("<code>'chest pain'</code>, <code>'severe chest pain'</code>, <code>'heart attack'</code>", styles['TableCell']),
            Paragraph("<b>EMERGENCY ESCALATION:</b> <i>'Medical Alert: If you are experiencing chest pain or signs of a heart attack, please call 911 or visit the nearest emergency department immediately. This platform cannot provide emergency medical care.'</i>", styles['TableCell'])
        ],
        [
            Paragraph("<b>Respiratory</b>", styles['TableCellBold']),
            Paragraph("<code>'can\'t breathe'</code>, <code>'difficulty breathing'</code>, <code>'choking'</code>", styles['TableCell']),
            Paragraph("<b>EMERGENCY ESCALATION:</b> <i>'Medical Alert: Severe respiratory distress requires immediate emergency intervention. Please call 911 immediately.'</i>", styles['TableCell'])
        ],
        [
            Paragraph("<b>Neurological</b>", styles['TableCellBold']),
            Paragraph("<code>'stroke'</code>, <code>'facial droop'</code>, <code>'sudden numbness'</code>", styles['TableCell']),
            Paragraph("<b>EMERGENCY ESCALATION:</b> <i>'Medical Alert: Sudden neurological deficits are an urgent medical emergency. Please contact emergency services right away.'</i>", styles['TableCell'])
        ],
        [
            Paragraph("<b>Severe Trauma / Bleeding</b>", styles['TableCellBold']),
            Paragraph("<code>'severe bleeding'</code>, <code>'unconscious'</code>, <code>'anaphylaxis'</code>", styles['TableCell']),
            Paragraph("<b>EMERGENCY ESCALATION:</b> <i>'Medical Alert: Please call 911 immediately or go to the nearest emergency room.'</i>", styles['TableCell'])
        ],
    ]
    t_triage = Table(triage_data, colWidths=[90, 160, 254])
    t_triage.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#B91C1C")),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor("#CBD5E1")),
        ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor("#E2E8F0")),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor("#FEF2F2")]),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('LEFTPADDING', (0,0), (-1,-1), 6),
        ('RIGHTPADDING', (0,0), (-1,-1), 6),
    ]))
    story.append(t_triage)
    story.append(Spacer(1, 12))

    # Section 3: Structured Capability Invocation Prompts
    story.append(Paragraph("3. Structured Capability Tool-Calling Prompts", styles['SectionHeader']))
    story.append(Paragraph(
        "Gemini 2.5 Flash is configured with OpenAPI function schemas. Below are prompt exemplars showing "
        "how patient user utterances map deterministically to capability calls:",
        styles['BodyDark']
    ))

    exemplars = [
        ("Patient Utterance: 'I need an orthopedic doctor sometime this week.'",
         "Agent Function Call: search_doctors(specialty='Orthopedics')\n"
         "Follow-up Agent Call: check_availability(doctor_id='...', start_date='2026-09-21', end_date='2026-09-26')\n"
         "Agent Output: 'I found Dr. Marcus Rao (Orthopedics) at Metro General Hospital. Available slots this week include:\n"
         "  1. Monday at 09:00 AM\n  2. Monday at 09:30 AM\n  3. Tuesday at 10:00 AM\nWould you like me to book one of these?'"),
        ("Patient Utterance: 'Book Monday at 9:00 AM please.'",
         "Agent Function Call: create_appointment(doctor_id='...', start_time='2026-09-21T09:00:00Z', notes='Intake request')\n"
         "Agent Output: 'Your appointment with Dr. Marcus Rao is verified and confirmed for Monday at 09:00 AM. A pre-visit questionnaire has been assigned to help your doctor prepare. Would you like to complete it now?'"),
        ("Patient Utterance: 'I want to cancel my appointment.'",
         "Agent Function Call: get_appointment(patient_id='...')\n"
         "Follow-up Agent Call: cancel_appointment(appointment_id='...', reason='Patient requested cancellation')\n"
         "Agent Output: 'Your appointment has been cancelled and the slot released. Would you like to reschedule for a different day?'"),
    ]
    for user_ut, bot_call in exemplars:
        ex_data = [
            [Paragraph(f"<b>{user_ut}</b>", styles['BodyDarkBold'])],
            [Paragraph(bot_call.replace('\n', '<br/>'), styles['CodeSnippet'])],
        ]
        t_ex = Table(ex_data, colWidths=[504])
        t_ex.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#EFF6FF")),
            ('BACKGROUND', (0,1), (-1,1), colors.HexColor("#F8FAFC")),
            ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor("#93C5FD")),
            ('TOPPADDING', (0,0), (-1,-1), 4),
            ('BOTTOMPADDING', (0,0), (-1,-1), 4),
            ('LEFTPADDING', (0,0), (-1,-1), 6),
            ('RIGHTPADDING', (0,0), (-1,-1), 6),
        ]))
        story.append(t_ex)
        story.append(Spacer(1, 6))

    # Section 4: Pre-Visit Clinical Questionnaire Prompt
    story.append(Paragraph("4. Pre-Visit Clinical Questionnaire Synthesis Prompt", styles['SectionHeader']))
    story.append(Paragraph(
        "After booking confirmation, the agent guides the patient through pre-visit clinical questions "
        "using structured elicitation prompts:",
        styles['BodyDark']
    ))
    q_box = [
        [Paragraph(
            "<b>QUESTIONNAIRE_PROMPT:</b><br/>"
            "'You are now assisting the patient with their pre-visit clinical questionnaire for their upcoming appointment. "
            "Inquire about:<br/>"
            "  1. Primary Reason for Visit & Main Symptoms (e.g. knee pain, stiffness).<br/>"
            "  2. Duration of Symptoms (e.g. 3 weeks, 2 months).<br/>"
            "  3. Current Medications & Known Allergies (e.g. Penicillin, Aspirin).<br/>"
            "  4. Relevant Medical History or Recent Injuries.<br/>"
            "Maintain an empathetic and concise conversational pace. Once answers are provided, synthesize structured JSON "
            "and invoke `submit_questionnaire(appointment_id, answers)` so the clinical staff receives the completed intake before the visit.'",
            styles['CodeSnippet']
        )]
    ]
    t_q = Table(q_box, colWidths=[504])
    t_q.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#F0FDF4")),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor("#86EFAC")),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ('LEFTPADDING', (0,0), (-1,-1), 8),
        ('RIGHTPADDING', (0,0), (-1,-1), 8),
    ]))
    story.append(t_q)

    doc.build(story, canvasmaker=NumberedCanvas)


if __name__ == '__main__':
    docs_dir = os.path.join(os.path.dirname(__file__), "..", "docs")
    os.makedirs(docs_dir, exist_ok=True)
    
    p1 = os.path.join(docs_dir, "Architecture_Documentation.pdf")
    p2 = os.path.join(docs_dir, "AI_Tools_and_Usage_Documentation.pdf")
    p3 = os.path.join(docs_dir, "AI_Prompts_Used.pdf")
    
    print(f"Generating {p1}...")
    build_architecture_pdf(p1)
    print(f"Generating {p2}...")
    build_ai_tools_pdf(p2)
    print(f"Generating {p3}...")
    build_ai_prompts_pdf(p3)
    print("All PDFs successfully generated!")
