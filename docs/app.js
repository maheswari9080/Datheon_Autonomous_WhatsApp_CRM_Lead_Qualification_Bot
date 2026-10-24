/* ==========================================================================
   Datheon Autonomous WhatsApp CRM & Lead Qualification Bot
   Interactive Client-Side Engine for GitHub Pages Portal
   ========================================================================== */

document.addEventListener("DOMContentLoaded", () => {
  initTabs();
  initSimulator();
  initApiConsole();
});

// ==========================================================================
// 1. Tab Navigation
// ==========================================================================
function initTabs() {
  const tabButtons = document.querySelectorAll(".tab-btn");
  const tabPanes = document.querySelectorAll(".tab-pane");

  tabButtons.forEach(btn => {
    btn.addEventListener("click", () => {
      const targetId = btn.getAttribute("data-tab");

      tabButtons.forEach(b => b.classList.remove("active"));
      tabPanes.forEach(p => p.classList.remove("active"));

      btn.classList.add("active");
      const targetPane = document.getElementById(targetId);
      if (targetPane) {
        targetPane.classList.add("active");
      }
    });
  });
}

// ==========================================================================
// 2. WhatsApp Simulator State Machine & Engine
// ==========================================================================
const simState = {
  fsm: "GREETING",
  dossier: {
    name: "Alex Vance",
    company: "Vance Technologies",
    budget: null,
    currency: "USD",
    team_size: null,
    authority: "Decision Maker",
    timeline: "Q4",
    score: 0,
    status: "DISCOVERY"
  },
  outbox: []
};

function initSimulator() {
  const chatInput = document.getElementById("chatInput");
  const btnSend = document.getElementById("btnSend");
  const quickChips = document.querySelectorAll(".chip-btn");

  if (btnSend && chatInput) {
    btnSend.addEventListener("click", () => handleUserMessage());
    chatInput.addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        handleUserMessage();
      }
    });
  }

  quickChips.forEach(chip => {
    chip.addEventListener("click", () => {
      const text = chip.getAttribute("data-prompt");
      if (text && chatInput) {
        chatInput.value = text;
        handleUserMessage();
      }
    });
  });

  updateDossierUI();
}

function handleUserMessage() {
  const chatInput = document.getElementById("chatInput");
  const text = chatInput.value.trim();
  if (!text) return;

  chatInput.value = "";
  appendBubble("user", text);

  // Bot response with small natural typing latency
  setTimeout(() => {
    processInboundMessage(text);
  }, 450);
}

function appendBubble(sender, text) {
  const container = document.getElementById("chatMessages");
  if (!container) return;

  const now = new Date();
  const timeStr = now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

  const bubble = document.createElement("div");
  bubble.className = `chat-bubble bubble-${sender}`;

  let checkmarks = sender === "user" ? '<span style="color:#3b82f6;">✓✓</span>' : '<span style="color:#059669;">✓✓</span>';

  bubble.innerHTML = `
    <div>${escapeHtml(text)}</div>
    <div class="bubble-meta">
      <span>${timeStr}</span>
      ${checkmarks}
    </div>
  `;

  container.appendChild(bubble);
  container.scrollTop = container.scrollHeight;
}

function processInboundMessage(text) {
  const lower = text.toLowerCase();

  // 1. Guardrail / Injection Check
  if (lower.includes("ignore previous instructions") || lower.includes("disregard") || lower.includes("override rules")) {
    simState.fsm = "HUMAN_HANDOFF";
    simState.dossier.score = 10;
    appendBubble("bot", "⚠️ Security notice: Potential prompt override detected. Our compliance guardrails have flagged this interaction. I am transferring this conversation to an engineering operator.");
    addOutboxEvent("slack.human_escalation", "Adversarial prompt injection attempt contained");
    updateDossierUI();
    return;
  }

  // 2. Human escalation request
  if (lower.includes("human") || lower.includes("agent") || lower.includes("operator") || lower.includes("representative")) {
    simState.fsm = "HUMAN_HANDOFF";
    appendBubble("bot", "Understood. I am connecting you directly with our senior solutions consultant right now. They have received your full context.");
    addOutboxEvent("slack.human_handoff", "Direct user handoff request dispatched");
    updateDossierUI();
    return;
  }

  // 3. Slot Booking confirmation
  if (simState.fsm === "QUALIFIED" && (lower.includes("tomorrow") || lower.includes("yes") || lower.includes("book") || lower.includes("3") || lower.includes("2"))) {
    simState.fsm = "BOOKED";
    simState.dossier.calendar_slot = "Tomorrow at 3:00 PM EST";
    appendBubble("bot", "🎉 Confirmed! I have booked your 30-min strategy session for **Tomorrow at 3:00 PM EST** via Google Calendar. You'll receive a calendar invitation and meeting link shortly!");
    addOutboxEvent("google_calendar.event_created", "Slot reserved (Tomorrow 3:00 PM)");
    addOutboxEvent("airtable.lead_upserted", "Lead record synced with Qualified status");
    addOutboxEvent("slack.demo_alert", "New high-intent demo booked");
    updateDossierUI();
    return;
  }

  // 4. BANT Information Extraction
  let extractedBudget = null;
  const budgetMatch = text.match(/\$?(\d{1,3}(?:,\d{3})+|\d+)\s*(k|thousand)?/i);
  if (budgetMatch) {
    let num = parseFloat(budgetMatch[1].replace(/,/g, ''));
    if (budgetMatch[2] && budgetMatch[2].toLowerCase().startsWith('k')) {
      num *= 1000;
    }
    extractedBudget = num;
  }

  const teamMatch = text.match(/(\d+)\s*(?:reps|sales|team|people|person|employees)/i);
  if (teamMatch) {
    simState.dossier.team_size = parseInt(teamMatch[1], 10);
  }

  if (extractedBudget !== null) {
    simState.dossier.budget = extractedBudget;
    if (extractedBudget >= 1000) {
      simState.fsm = "QUALIFIED";
      simState.dossier.score = 94;
      appendBubble("bot", `Fantastic! With an annual budget of $${extractedBudget.toLocaleString()} and your team requirements, you qualify for our Enterprise Acceleration tier! 🚀\n\nWould tomorrow at 3:00 PM EST work for a live architecture demonstration?`);
    } else {
      simState.fsm = "NOT_QUALIFIED";
      simState.dossier.score = 35;
      appendBubble("bot", `Thank you for sharing your budget details. Our Enterprise qualification threshold starts at $1,000/year. We recommend exploring our self-serve developer tier documentation!`);
    }
  } else {
    // Missing budget
    simState.fsm = "NEEDS_INFORMATION";
    simState.dossier.score = 55;
    appendBubble("bot", "Thanks for reaching out! To pair you with the right solution architect, what estimated annual budget does your team have allocated for sales automation?");
  }

  updateDossierUI();
}

function updateDossierUI() {
  const fsmBadge = document.getElementById("fsmStateBadge");
  const scoreVal = document.getElementById("scoreValue");
  const budgetVal = document.getElementById("valBudget");
  const teamVal = document.getElementById("valTeam");
  const timelineVal = document.getElementById("valTimeline");
  const statusVal = document.getElementById("valStatus");

  if (fsmBadge) {
    fsmBadge.className = `state-badge state-${simState.fsm}`;
    fsmBadge.textContent = simState.fsm;
  }

  if (scoreVal) {
    scoreVal.textContent = `${simState.dossier.score}/100`;
  }

  if (budgetVal) {
    budgetVal.textContent = simState.dossier.budget ? `$${simState.dossier.budget.toLocaleString()}` : "Pending input";
  }

  if (teamVal) {
    teamVal.textContent = simState.dossier.team_size ? `${simState.dossier.team_size} reps` : "50 reps";
  }

  if (timelineVal) {
    timelineVal.textContent = simState.dossier.timeline;
  }

  if (statusVal) {
    statusVal.textContent = simState.fsm === "QUALIFIED" || simState.fsm === "BOOKED" ? "High-Intent Enterprise" : "In Progress";
  }
}

function addOutboxEvent(eventType, description) {
  const list = document.getElementById("outboxEventList");
  if (!list) return;

  const item = document.createElement("div");
  item.className = "event-log-item";
  item.innerHTML = `
    <span style="font-size: 15px;">⚡</span>
    <div>
      <div style="font-weight: 700; color: #0f172a;">${escapeHtml(eventType)}</div>
      <div style="font-size: 11px; color: #64748b;">${escapeHtml(description)}</div>
    </div>
  `;
  list.prepend(item);
}

// ==========================================================================
// 3. API Console Mock Simulator
// ==========================================================================
function initApiConsole() {
  const endpointSelect = document.getElementById("apiEndpointSelect");
  const btnExecuteApi = document.getElementById("btnExecuteApi");
  const apiOutput = document.getElementById("apiOutput");

  if (!endpointSelect || !btnExecuteApi || !apiOutput) return;

  const mockResponses = {
    "get_health": {
      status_code: 200,
      headers: { "content-type": "application/json" },
      body: {
        status: "healthy",
        version: "1.0.0",
        database: "connected (async SQLite/PostgreSQL)",
        outbox_worker: "active",
        timestamp: new Date().toISOString()
      }
    },
    "post_webhook": {
      status_code: 200,
      headers: { "content-type": "application/json", "x-signature-status": "verified" },
      body: {
        status: "acknowledged",
        meta_message_id: "wamid.HBgLMjAyNjEwMjQ0OTQzFQIAERgSMzNF",
        latency_ms: 18.4,
        outbox_enqueued: true
      }
    },
    "get_escalations": {
      status_code: 200,
      headers: { "content-type": "application/json" },
      body: {
        total_open: 1,
        items: [
          {
            escalation_id: "esc-9082",
            lead_phone: "+1 (555) 019-2834",
            reason: "PROMPT_INJECTION_FLAGGED",
            score: 10,
            status: "OPEN",
            dossier: {
              company: "Vance Technologies",
              budget: 25000,
              authority: "Decision Maker"
            }
          }
        ]
      }
    }
  };

  btnExecuteApi.addEventListener("click", () => {
    const selected = endpointSelect.value;
    const resp = mockResponses[selected] || mockResponses["get_health"];
    apiOutput.textContent = JSON.stringify(resp, null, 2);
  });
}

function escapeHtml(str) {
  return str.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}
