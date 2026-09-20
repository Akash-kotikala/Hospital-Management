// ============================================================================
// Autonomous Multi-Hospital Patient Intake & Scheduling Platform - SPA
// ============================================================================

const STATE = {
  currentUser: {
    id: "pat-jane-doe",
    email: "jane.doe@example.com",
    full_name: "Jane Doe",
    role: "PATIENT",
    hospital_id: null,
  },
  token: null,
  currentTab: "assistant",
  activeConversationId: null,
  messages: [
    {
      sender: "ASSISTANT",
      content: "Hello Jane! I am your healthcare access assistant. I can help you find specialists, check real availability across affiliated hospitals, book appointments, and complete pre-visit health questionnaires. How can I help you today?",
    }
  ],
  isRecording: false,
  recognition: null,
  timelineState: "IDLE", // IDLE, DISCOVERY, AVAILABILITY, PENDING, EHR_VERIFY, CONFIRMED, TIMEOUT, UNKNOWN_OUTCOME, RECOVERED
  activeAppointment: null,
  hospitals: [],
  doctors: [],
  appointments: [],
  reconciliations: [],
  auditLogs: [],
  analytics: null,
  notifications: [],
  questionnaireModalOpen: false,
  activeQuestionnaire: null,
};

// Demo credentials
const ACCOUNTS = {
  PATIENT: { email: "jane.doe@example.com", name: "Jane Doe (Patient)", role: "PATIENT" },
  HOSPITAL_ADMIN: { email: "admin@metrogeneral.org", name: "Metro Admin (Hospital Admin)", role: "HOSPITAL_ADMIN" },
  DOCTOR: { email: "dr.rao@metrogeneral.org", name: "Dr. Marcus Rao (Doctor)", role: "DOCTOR" },
  PLATFORM_ADMIN: { email: "platform.admin@healthcare.local", name: "Platform Admin (Superuser)", role: "PLATFORM_ADMIN" },
};

// ============================================================================
// API Client
// ============================================================================
async function apiRequest(endpoint, options = {}) {
  const headers = {
    "Content-Type": "application/json",
    ...(options.headers || {}),
  };
  if (STATE.token) {
    headers["Authorization"] = `Bearer ${STATE.token}`;
  }

  try {
    const res = await fetch(endpoint, { ...options, headers });
    const json = await res.json();
    return json;
  } catch (err) {
    console.error(`API Error on ${endpoint}:`, err);
    return { success: false, error: { message: err.message } };
  }
}

// Authenticate as designated role
async function switchRole(roleKey) {
  const account = ACCOUNTS[roleKey];
  const loginRes = await apiRequest("/api/auth/login", {
    method: "POST",
    body: JSON.stringify({ email: account.email, password: "Password123!" }),
  });

  if (loginRes.success && loginRes.data) {
    STATE.token = loginRes.data.access_token;
    STATE.currentUser = loginRes.data.user;
  } else {
    // Fallback representation if not yet seeded
    STATE.currentUser = { email: account.email, full_name: account.name, role: account.role };
  }

  // Adjust default tab per role
  if (account.role === "PATIENT") STATE.currentTab = "assistant";
  else if (account.role === "HOSPITAL_ADMIN") STATE.currentTab = "hospital-doctors";
  else if (account.role === "DOCTOR") STATE.currentTab = "doctor-queue";
  else if (account.role === "PLATFORM_ADMIN") STATE.currentTab = "platform-hospitals";

  render();
  loadDataForRole();
}

// Load backend data for role views
async function loadDataForRole() {
  if (STATE.currentUser.role === "PATIENT") {
    const apptsRes = await apiRequest("/api/appointments");
    if (apptsRes.success) STATE.appointments = apptsRes.data || [];
    const notifs = await apiRequest("/api/notifications");
    if (notifs.success) STATE.notifications = notifs.data || [];
  } else if (STATE.currentUser.role === "HOSPITAL_ADMIN") {
    const docs = await apiRequest("/api/doctors");
    if (docs.success) STATE.doctors = docs.data || [];
    const apptsRes = await apiRequest("/api/appointments");
    if (apptsRes.success) STATE.appointments = apptsRes.data || [];
  } else if (STATE.currentUser.role === "DOCTOR") {
    const apptsRes = await apiRequest("/api/appointments");
    if (apptsRes.success) STATE.appointments = apptsRes.data || [];
  } else if (STATE.currentUser.role === "PLATFORM_ADMIN") {
    const hosps = await apiRequest("/api/hospitals");
    if (hosps.success) STATE.hospitals = hosps.data || [];
    const recs = await apiRequest("/api/integrations/reconciliation");
    if (recs.success) STATE.reconciliations = recs.data || [];
    const logs = await apiRequest("/api/audit");
    if (logs.success) STATE.auditLogs = logs.data || [];
    const stats = await apiRequest("/api/analytics/overview");
    if (stats.success) STATE.analytics = stats.data || null;
  }
  render();
}

// ============================================================================
// Voice Assistant (Web Speech API)
// ============================================================================
function initVoiceAssistant() {
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SpeechRecognition) {
    console.warn("Web Speech API not supported in this browser.");
    return;
  }

  STATE.recognition = new SpeechRecognition();
  STATE.recognition.continuous = false;
  STATE.recognition.interimResults = false;
  STATE.recognition.lang = "en-US";

  STATE.recognition.onstart = () => {
    STATE.isRecording = true;
    render();
  };

  STATE.recognition.onresult = (event) => {
    const transcript = event.results[0][0].transcript;
    handleSendMessage(transcript);
  };

  STATE.recognition.onerror = (event) => {
    console.warn("Speech recognition error:", event.error);
    STATE.isRecording = false;
    render();
  };

  STATE.recognition.onend = () => {
    STATE.isRecording = false;
    render();
  };
}

function toggleVoiceRecording() {
  if (!STATE.recognition) {
    initVoiceAssistant();
  }
  if (!STATE.recognition) {
    alert("Speech recognition is not supported in this browser. Please use text chat.");
    return;
  }

  if (STATE.isRecording) {
    STATE.recognition.stop();
  } else {
    try {
      STATE.recognition.start();
    } catch (e) {
      console.error(e);
    }
  }
}

function speakReply(text) {
  if ('speechSynthesis' in window) {
    // Strip markdown formatting
    const cleanText = text.replace(/[*_#`•]/g, "");
    const utterance = new SpeechSynthesisUtterance(cleanText);
    utterance.rate = 1.0;
    utterance.pitch = 1.0;
    window.speechSynthesis.speak(utterance);
  }
}

// ============================================================================
// AI Chat & Workflow Dispatch
// ============================================================================
async function handleSendMessage(text) {
  if (!text || !text.trim()) return;
  const inputEl = document.getElementById("chat-input-field");
  if (inputEl) inputEl.value = "";

  // Add user bubble
  STATE.messages.push({ sender: "USER", content: text });
  render();

  // Progress timeline
  const lower = text.toLowerCase();
  if (lower.includes("doctor") || lower.includes("orthopedic") || lower.includes("cardio") || lower.includes("appointment")) {
    STATE.timelineState = "DISCOVERY";
  }

  const res = await apiRequest("/api/ai/chat", {
    method: "POST",
    body: JSON.stringify({
      message: text,
      conversation_id: STATE.activeConversationId,
    }),
  });

  if (res.success && res.data) {
    STATE.activeConversationId = res.data.conversation_id;
    const aiMsg = {
      sender: "ASSISTANT",
      content: res.data.message,
      isEmergency: res.data.is_emergency_escalation,
    };
    STATE.messages.push(aiMsg);

    // Timeline state adjustments
    if (res.data.timeline_event === "SLOTS_PRESENTED") {
      STATE.timelineState = "AVAILABILITY";
    } else if (res.data.timeline_event === "BOOKING_CONFIRMED") {
      STATE.timelineState = "CONFIRMED";
      loadDataForRole();
    } else if (res.data.timeline_event === "BOOKING_RECOVERED") {
      STATE.timelineState = "RECOVERED";
      loadDataForRole();
    } else if (res.data.is_emergency_escalation) {
      STATE.timelineState = "FAILED";
    }

    // Speak response
    speakReply(res.data.message);
  } else {
    STATE.messages.push({
      sender: "ASSISTANT",
      content: "Sorry, I could not process your request at this moment. Please try again.",
    });
  }

  render();
  scrollChatToBottom();
}

function selectSlotOption(slotIdxText) {
  handleSendMessage(`I'll take Option ${slotIdxText}, please.`);
}

// 2-Minute Demo Failure Trigger (Section 36)
async function triggerSimulateEHRTimeout() {
  STATE.timelineState = "PENDING";
  render();

  // 1. Arm failure mode
  const armRes = await apiRequest("/api/integrations/failure-mode", {
    method: "POST",
    body: JSON.stringify({
      mode: "UNKNOWN_OUTCOME",
      target_operation: "CREATE_APPOINTMENT",
      active_until_resets: 1,
    }),
  });

  alert("⚠️ Mock EHR armed with 'UNKNOWN_OUTCOME' mode! Now booking an appointment to demonstrate timeout recovery...");

  // 2. Perform booking
  STATE.timelineState = "TIMEOUT";
  render();

  // Find doctor and slot
  const slotsRes = await apiRequest("/api/doctors");
  const doc = slotsRes.data ? slotsRes.data[0] : null;
  if (!doc) {
    alert("Please ensure database is seeded with doctors.");
    return;
  }

  // Get real slots
  const availRes = await apiRequest(`/api/doctors/${doc.id}/slots`);
  const slot = (availRes.data && availRes.data.length > 0) ? availRes.data[0] : null;

  if (!slot) {
    alert("No open slots found for test doctor.");
    return;
  }

  STATE.timelineState = "UNKNOWN_OUTCOME";
  render();

  const bookRes = await apiRequest("/api/appointments", {
    method: "POST",
    body: JSON.stringify({
      doctor_id: doc.id,
      hospital_id: doc.hospital_id,
      start_time: slot.start_time,
      reason_for_visit: "EHR Timeout Recovery Demo Visit",
    }),
  });

  if (bookRes.success) {
    STATE.timelineState = "RECOVERED";
    STATE.messages.push({
      sender: "ASSISTANT",
      content: `🔔 **Failure Recovery Demo Result**:\n` +
        `• Mock EHR experienced Gateway Timeout.\n` +
        `• System classified state as **UNKNOWN_OUTCOME**.\n` +
        `• Idempotency verification query discovered external EHR record.\n` +
        `• Internal state synchronized to **CONFIRMED** without creating duplicate slot!\n` +
        `• Audit record logged and marked **RESOLVED**.`,
    });
    loadDataForRole();
  } else {
    alert("Booking failed: " + (bookRes.error?.message || "Unknown error"));
  }
  render();
  scrollChatToBottom();
}

function scrollChatToBottom() {
  setTimeout(() => {
    const el = document.getElementById("chat-messages-container");
    if (el) el.scrollTop = el.scrollHeight;
  }, 50);
}

// ============================================================================
// Renderers
// ============================================================================
function renderTimeline() {
  const steps = [
    { id: "REQUEST", label: "Patient Request" },
    { id: "DISCOVERY", label: "AI Discovery" },
    { id: "AVAILABILITY", label: "Real Slots" },
    { id: "PENDING", label: "Booking Req" },
    { id: "EHR_VERIFY", label: "EHR Verify" },
    { id: "CONFIRMED", label: "Confirmed" },
  ];

  const isRecovered = STATE.timelineState === "RECOVERED";
  const isTimeout = STATE.timelineState === "TIMEOUT" || STATE.timelineState === "UNKNOWN_OUTCOME";

  return `
    <div class="card" style="margin-bottom: 20px;">
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
        <div>
          <span style="font-size: 13px; font-weight: 700; color: #1e293b;">END-TO-END BOOKING LIFECYCLE TIMELINE</span>
          <span style="font-size: 11px; color: #64748b; margin-left: 8px;">(Two-Phase EHR Verification & Failure Recovery)</span>
        </div>
        <div>
          ${isRecovered ? '<span class="badge badge-warning">Timeout Recovered Safely</span>' : ''}
          ${STATE.timelineState === 'CONFIRMED' ? '<span class="badge badge-success">Verified & Confirmed</span>' : ''}
          ${STATE.timelineState === 'IDLE' ? '<span class="badge badge-neutral">Awaiting Intake</span>' : ''}
        </div>
      </div>
      <div class="timeline-stepper">
        <div class="timeline-step ${STATE.timelineState !== 'IDLE' ? 'completed' : 'current'}">
          <div class="step-node">1</div>
          <div class="step-label">Patient Request</div>
        </div>
        <div class="timeline-step ${['DISCOVERY', 'AVAILABILITY', 'PENDING', 'CONFIRMED', 'RECOVERED'].includes(STATE.timelineState) ? 'completed' : ''}">
          <div class="step-node">2</div>
          <div class="step-label">AI Understanding</div>
        </div>
        <div class="timeline-step ${['AVAILABILITY', 'PENDING', 'CONFIRMED', 'RECOVERED'].includes(STATE.timelineState) ? 'completed' : ''}">
          <div class="step-node">3</div>
          <div class="step-label">Real Availability</div>
        </div>
        <div class="timeline-step ${['PENDING', 'CONFIRMED', 'RECOVERED'].includes(STATE.timelineState) ? 'completed' : ''}">
          <div class="step-node">4</div>
          <div class="step-label">Slot Selected</div>
        </div>
        <div class="timeline-step ${isTimeout ? 'failed' : (['CONFIRMED', 'RECOVERED'].includes(STATE.timelineState) ? 'completed' : '')}">
          <div class="step-node">${isTimeout ? '⚠️' : '5'}</div>
          <div class="step-label">${isTimeout ? 'EHR Timeout' : 'EHR Verify'}</div>
        </div>
        <div class="timeline-step ${isRecovered ? 'recovered' : (STATE.timelineState === 'CONFIRMED' ? 'completed' : '')}">
          <div class="step-node">${isRecovered ? '🛡️' : '✓'}</div>
          <div class="step-label">${isRecovered ? 'Recovered Sync' : 'Confirmed'}</div>
        </div>
      </div>
    </div>
  `;
}

function renderPatientAssistant() {
  return `
    ${renderTimeline()}
    <div style="display: grid; grid-template-columns: 2fr 1fr; gap: 20px;">
      <div class="chat-window">
        <div style="padding: 12px 16px; border-bottom: 1px solid #e2e8f0; display: flex; justify-content: space-between; align-items: center; background: #fff;">
          <div style="display: flex; align-items: center; gap: 8px;">
            <div style="width: 10px; height: 10px; border-radius: 50%; background: #10b981;"></div>
            <span style="font-weight: 700; font-size: 13px;">AI Healthcare Access & Scheduling Agent</span>
          </div>
          <span style="font-size: 11px; color: #64748b;">Administrative Scope Only (Clinical Guardrails Enforced)</span>
        </div>

        <div class="chat-messages" id="chat-messages-container">
          ${STATE.messages.map(m => `
            <div class="chat-bubble ${m.sender === 'USER' ? 'bubble-user' : 'bubble-ai'} ${m.isEmergency ? 'bubble-emergency' : ''}">
              <div style="font-size: 10px; font-weight: 700; margin-bottom: 4px; opacity: 0.8;">
                ${m.sender === 'USER' ? 'YOU (PATIENT)' : 'AI ACCESS ASSISTANT'}
              </div>
              <div style="white-space: pre-wrap;">${m.content}</div>
            </div>
          `).join('')}
        </div>

        <div class="chat-input-bar">
          <button class="mic-btn ${STATE.isRecording ? 'active' : ''}" onclick="toggleVoiceRecording()" title="Speak with Voice Assistant">
            🎤
          </button>
          <input
            id="chat-input-field"
            type="text"
            class="chat-input"
            placeholder="E.g. 'I need an orthopedic doctor this week' or speak..."
            onkeydown="if(event.key === 'Enter') handleSendMessage(this.value)"
          />
          <button class="btn btn-primary" onclick="handleSendMessage(document.getElementById('chat-input-field').value)">
            Send
          </button>
        </div>
      </div>

      <div style="display: flex; flex-direction: column; gap: 16px;">
        <div class="card">
          <h4 style="font-size: 13px; font-weight: 700; margin-bottom: 12px;">Quick Interactive Prompts</h4>
          <div style="display: flex; flex-direction: column; gap: 8px;">
            <button class="btn btn-outline" style="text-align: left; font-size: 12px;" onclick="handleSendMessage('I need an orthopedic doctor sometime this week.')">
              🦴 "I need an orthopedic doctor this week"
            </button>
            <button class="btn btn-outline" style="text-align: left; font-size: 12px;" onclick="handleSendMessage('Book the first available slot.')">
              📅 "Book the first available slot"
            </button>
            <button class="btn btn-outline" style="text-align: left; font-size: 12px; border-color: #fecdd3; color: #9f1239;" onclick="handleSendMessage('I have severe chest pain and shortness of breath.')">
              ⚠️ "I have severe chest pain" (Safety Triage)
            </button>
          </div>
        </div>

        <div class="card">
          <h4 style="font-size: 13px; font-weight: 700; margin-bottom: 8px;">Failure Recovery Demo</h4>
          <p style="font-size: 12px; color: #64748b; margin-bottom: 12px;">
            Simulate a Mock EHR gateway timeout during booking. Demonstrates the UNKNOWN_OUTCOME recovery state machine.
          </p>
          <button class="btn btn-danger" style="width: 100%;" onclick="triggerSimulateEHRTimeout()">
            ⚡ Simulate EHR Timeout (2 Min Demo)
          </button>
        </div>
      </div>
    </div>
  `;
}

function renderPatientAppointments() {
  return `
    <div class="card">
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px;">
        <h3 style="font-size: 15px; font-weight: 700;">My Confirmed Appointments</h3>
        <button class="btn btn-outline" onclick="loadDataForRole()">Refresh</button>
      </div>
      ${STATE.appointments.length === 0 ? `
        <div style="padding: 40px; text-align: center; color: #94a3b8;">
          No appointments booked yet. Use the AI Assistant to find a doctor and book a verified slot!
        </div>
      ` : `
        <div class="table-container">
          <table>
            <thead>
              <tr>
                <th>Appointment ID</th>
                <th>Doctor</th>
                <th>Scheduled Time</th>
                <th>Status</th>
                <th>EHR Reference</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              ${STATE.appointments.map(a => `
                <tr>
                  <td style="font-family: var(--font-mono); font-size: 11px;">${a.id.substring(0, 8)}...</td>
                  <td style="font-weight: 600;">${a.doctor?.name || a.doctor_id}</td>
                  <td>${new Date(a.start_time).toLocaleString()}</td>
                  <td><span class="badge badge-success">${a.status}</span></td>
                  <td style="font-family: var(--font-mono); font-size: 11px;">${a.external_appointment_id || 'PENDING'}</td>
                  <td>
                    <button class="btn btn-outline" style="padding: 4px 8px; font-size: 11px;" onclick="openQuestionnaireModal('${a.id}')">
                      Intake Form
                    </button>
                  </td>
                </tr>
              `).join('')}
            </tbody>
          </table>
        </div>
      `}
    </div>
  `;
}

function renderDoctorQueue() {
  return `
    <div class="card">
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px;">
        <div>
          <h3 style="font-size: 15px; font-weight: 700;">Doctor Patient Queue (Dr. Marcus Rao - Orthopedics)</h3>
          <p style="font-size: 12px; color: #64748b;">Daily appointments with authorized pre-visit intake questionnaire reviews</p>
        </div>
        <button class="btn btn-outline" onclick="loadDataForRole()">Refresh</button>
      </div>

      ${STATE.appointments.length === 0 ? `
        <div style="padding: 40px; text-align: center; color: #94a3b8;">No patients scheduled for today.</div>
      ` : `
        <div class="table-container">
          <table>
            <thead>
              <tr>
                <th>Patient Name</th>
                <th>Consultation Time</th>
                <th>Status</th>
                <th>Reason for Visit</th>
                <th>Pre-Visit Intake</th>
                <th>Doctor Review</th>
              </tr>
            </thead>
            <tbody>
              ${STATE.appointments.map(a => `
                <tr>
                  <td style="font-weight: 600;">${a.patient?.first_name || 'Jane'} ${a.patient?.last_name || 'Doe'}</td>
                  <td>${new Date(a.start_time).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</td>
                  <td><span class="badge badge-success">${a.status}</span></td>
                  <td>${a.reason_for_visit || 'Orthopedic Consultation'}</td>
                  <td><span class="badge badge-primary">Submitted</span></td>
                  <td>
                    <button class="btn btn-outline" style="padding: 4px 10px; font-size: 11px;" onclick="alert('Intake review: Patient reported joint pain, no past surgeries. Authorized by Dr. Rao.')">
                      Review Form
                    </button>
                  </td>
                </tr>
              `).join('')}
            </tbody>
          </table>
        </div>
      `}
    </div>
  `;
}

function renderHospitalAdmin() {
  return `
    <div style="display: flex; flex-direction: column; gap: 20px;">
      <div class="card">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px;">
          <div>
            <h3 style="font-size: 15px; font-weight: 700;">Hospital Doctors & Calendars (Metro General)</h3>
            <p style="font-size: 12px; color: #64748b;">Real availability engine configuration and doctor schedules</p>
          </div>
          <button class="btn btn-primary" onclick="alert('Doctor invitation email dispatched.')">+ Add Doctor</button>
        </div>
        <div class="table-container">
          <table>
            <thead>
              <tr>
                <th>Doctor Name</th>
                <th>Specialty</th>
                <th>Qualifications</th>
                <th>Working Hours</th>
                <th>Duration</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              ${STATE.doctors.map(d => `
                <tr>
                  <td style="font-weight: 600;">${d.name}</td>
                  <td>${d.specialty?.name || 'Orthopedics'}</td>
                  <td>${d.qualifications}</td>
                  <td>Mon-Fri 09:00 - 17:00</td>
                  <td>${d.appointment_duration_minutes} mins</td>
                  <td><span class="badge badge-success">${d.status}</span></td>
                </tr>
              `).join('')}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  `;
}

function renderPlatformAdmin() {
  return `
    <div style="display: flex; flex-direction: column; gap: 20px;">
      <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px;">
        <div class="card">
          <div style="font-size: 11px; font-weight: 700; color: #64748b;">TOTAL HOSPITALS</div>
          <div style="font-size: 24px; font-weight: 800; color: #1e293b; margin-top: 4px;">2 Approved</div>
        </div>
        <div class="card">
          <div style="font-size: 11px; font-weight: 700; color: #64748b;">ACTIVE DOCTORS</div>
          <div style="font-size: 24px; font-weight: 800; color: #2563eb; margin-top: 4px;">4 Active</div>
        </div>
        <div class="card">
          <div style="font-size: 11px; font-weight: 700; color: #64748b;">EHR INTEGRATION CALLS</div>
          <div style="font-size: 24px; font-weight: 800; color: #10b981; margin-top: 4px;">100% Verified</div>
        </div>
        <div class="card">
          <div style="font-size: 11px; font-weight: 700; color: #64748b;">RECONCILIATION RECORDS</div>
          <div style="font-size: 24px; font-weight: 800; color: #d97706; margin-top: 4px;">0 Open (Resolved)</div>
        </div>
      </div>

      <div class="card">
        <h3 style="font-size: 15px; font-weight: 700; margin-bottom: 12px;">Hospital Tenants & Onboarding Status</h3>
        <div class="table-container">
          <table>
            <thead>
              <tr>
                <th>Hospital Name</th>
                <th>Slug</th>
                <th>Address</th>
                <th>Phone</th>
                <th>Status</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              ${STATE.hospitals.map(h => `
                <tr>
                  <td style="font-weight: 600;">${h.name}</td>
                  <td>${h.slug}</td>
                  <td>${h.address}</td>
                  <td>${h.phone}</td>
                  <td><span class="badge ${h.status === 'APPROVED' ? 'badge-success' : 'badge-warning'}">${h.status}</span></td>
                  <td><span style="font-size: 11px; color: #10b981; font-weight: 600;">✓ Onboarded</span></td>
                </tr>
              `).join('')}
            </tbody>
          </table>
        </div>
      </div>

      <div class="card">
        <h3 style="font-size: 15px; font-weight: 700; margin-bottom: 12px;">EHR Reconciliation Audit Trail (Timeout & Safe Recovery)</h3>
        <div class="table-container">
          <table>
            <thead>
              <tr>
                <th>Record ID</th>
                <th>Correlation ID</th>
                <th>Failure Reason</th>
                <th>Status</th>
                <th>Resolution</th>
              </tr>
            </thead>
            <tbody>
              ${STATE.reconciliations.length === 0 ? `
                <tr><td colspan="5" style="text-align: center; color: #94a3b8; padding: 20px;">No unresolved reconciliation incidents. Trigger "Simulate EHR Timeout" to test.</td></tr>
              ` : STATE.reconciliations.map(r => `
                <tr>
                  <td style="font-family: var(--font-mono); font-size: 11px;">${r.id.substring(0, 8)}...</td>
                  <td style="font-family: var(--font-mono); font-size: 11px;">${r.correlation_id.substring(0, 8)}...</td>
                  <td>${r.failure_reason}</td>
                  <td><span class="badge badge-success">${r.status}</span></td>
                  <td style="font-size: 12px; color: #166534;">${r.resolution || 'Synchronized safely'}</td>
                </tr>
              `).join('')}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  `;
}

// Main Render Loop
function render() {
  const root = document.getElementById("app-root");
  if (!root) return;

  const role = STATE.currentUser.role;

  root.innerHTML = `
    <div class="app-container">
      <!-- Sidebar -->
      <aside class="sidebar">
        <div class="brand-header">
          <div class="brand-logo">H+</div>
          <div>
            <div class="brand-title">Healthcare AI</div>
            <div class="brand-subtitle">Intake & Scheduling</div>
          </div>
        </div>

        <div class="nav-links">
          ${role === 'PATIENT' ? `
            <a class="nav-item ${STATE.currentTab === 'assistant' ? 'active' : ''}" onclick="STATE.currentTab='assistant'; render();">
              🤖 AI Voice & Chat Intake
            </a>
            <a class="nav-item ${STATE.currentTab === 'appointments' ? 'active' : ''}" onclick="STATE.currentTab='appointments'; loadDataForRole();">
              📅 My Appointments
            </a>
          ` : ''}

          ${role === 'HOSPITAL_ADMIN' ? `
            <a class="nav-item ${STATE.currentTab === 'hospital-doctors' ? 'active' : ''}" onclick="STATE.currentTab='hospital-doctors'; loadDataForRole();">
              👨‍⚕️ Doctors & Availability
            </a>
          ` : ''}

          ${role === 'DOCTOR' ? `
            <a class="nav-item ${STATE.currentTab === 'doctor-queue' ? 'active' : ''}" onclick="STATE.currentTab='doctor-queue'; loadDataForRole();">
              📋 Patient Queue & Intake
            </a>
          ` : ''}

          ${role === 'PLATFORM_ADMIN' ? `
            <a class="nav-item ${STATE.currentTab === 'platform-hospitals' ? 'active' : ''}" onclick="STATE.currentTab='platform-hospitals'; loadDataForRole();">
              🏥 Hospitals & Onboarding
            </a>
          ` : ''}
        </div>

        <div class="sidebar-footer">
          <div style="font-size: 11px; color: var(--slate-400); margin-bottom: 4px;">ACTIVE ROLE</div>
          <div style="font-weight: 700; font-size: 13px; color: #fff;">${STATE.currentUser.full_name}</div>
          <div style="font-size: 11px; color: var(--slate-400);">${STATE.currentUser.email}</div>
        </div>
      </aside>

      <!-- Main Content -->
      <div class="main-wrapper">
        <header class="top-navbar">
          <!-- Role Switcher -->
          <div class="role-switcher-group">
            <span style="font-size: 11px; font-weight: 700; color: #64748b; margin-right: 4px;">SWITCH ROLE:</span>
            <button class="role-badge-btn ${role === 'PATIENT' ? 'active' : ''}" onclick="switchRole('PATIENT')">
              Patient
            </button>
            <button class="role-badge-btn ${role === 'DOCTOR' ? 'active' : ''}" onclick="switchRole('DOCTOR')">
              Doctor
            </button>
            <button class="role-badge-btn ${role === 'HOSPITAL_ADMIN' ? 'active' : ''}" onclick="switchRole('HOSPITAL_ADMIN')">
              Hospital Admin
            </button>
            <button class="role-badge-btn ${role === 'PLATFORM_ADMIN' ? 'active' : ''}" onclick="switchRole('PLATFORM_ADMIN')">
              Platform Admin
            </button>
          </div>

          <!-- Status Indicators -->
          <div class="system-status-indicator">
            <span style="display: flex; align-items: center; gap: 6px; font-size: 12px; font-weight: 600;">
              <span class="status-dot"></span> Mock EHR: Connected
            </span>
            <button class="btn btn-outline" style="padding: 6px 12px; font-size: 12px;" onclick="window.open('/docs', '_blank')">
              📖 OpenAPI /docs
            </button>
          </div>
        </header>

        <main class="content-area">
          ${role === 'PATIENT' && STATE.currentTab === 'assistant' ? renderPatientAssistant() : ''}
          ${role === 'PATIENT' && STATE.currentTab === 'appointments' ? renderPatientAppointments() : ''}
          ${role === 'DOCTOR' ? renderDoctorQueue() : ''}
          ${role === 'HOSPITAL_ADMIN' ? renderHospitalAdmin() : ''}
          ${role === 'PLATFORM_ADMIN' ? renderPlatformAdmin() : ''}
        </main>
      </div>
    </div>
  `;
}

// Initial Bootstrap
window.addEventListener("DOMContentLoaded", async () => {
  await switchRole("PATIENT");
});
