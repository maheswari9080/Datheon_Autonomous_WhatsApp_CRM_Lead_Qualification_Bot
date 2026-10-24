# System Architecture & Technical Specifications

## Framework: RACE + CO-STAR + PACT + STRIDE + TDD
### Datheon Autonomous WhatsApp CRM Lead Qualification Bot

---

## 1. Architectural Foundations (SOLID & Clean Architecture)

The system adheres to Clean Architecture principles, isolating the business domain from external delivery channels and infrastructure adapters:

```
src/
├── core/         # Config, security, crypto, structured logging, custom exceptions
├── database/     # SQLAlchemy 2.0 async declarative models & session management
├── fsm/          # Finite State Machine engine & transition rules
├── webhook/      # Meta WhatsApp Cloud API endpoint, signature verifier, parser, deduplicator
├── ai/           # Pydantic V2 schemas, LLM provider adapter, injection guardrails, qualification policy
├── calendar/     # Calendar adapter interfaces (Google Calendar, Cal.com), slot conflict resolver
├── crm/          # CRM adapter interface (Airtable), transactional outbox worker
├── escalation/   # Escalation controller, sentiment analyzer, Slack dispatcher
└── api/          # Administrative & telemetry management endpoints
```

---

## 2. PACT Workflow Model

- **Purpose**: Fully automate conversational lead qualification and demonstration booking without human intervention, while maintaining absolute data integrity, zero false positives, and immediate human escalation upon anomaly.
- **Actors**:
  1. *WhatsApp Prospect*: Interacts via natural language, buttons, and list pickers.
  2. *Autonomous Qualification Engine*: Extracts attributes, calculates qualification score, and drives conversation.
  3. *Calendar Engine*: Surfaces verified real-time availability and confirms bookings.
  4. *CRM Synchronizer*: Ensures lead status, conversation notes, and booking IDs persist reliably.
  5. *Human Sales Representative*: Receives escalated conversations with comprehensive briefing dossiers.
- **Components**: Webhook Ingestion, FSM Controller, AI Extractor, Calendar Scheduler, Transactional Outbox, Escalation Manager.
- **Transitions**: Deterministic state machine governing conversational states from `NEW` to `BOOKED` or `HUMAN_HANDOFF`.

---

## 3. Distributed Workflow Reliability (Transactional Outbox)

To prevent distributed transaction failures (e.g. Calendar event created but CRM update fails, or WhatsApp notification dropped):
1. State changes and outbound events are written to the `outbox_events` table within the same ACID database transaction.
2. An asynchronous outbox background processor polls for pending events, executes external network calls with exponential backoff and jitter, and marks events `PROCESSED`.
3. If an external service is unavailable after maximum retries, the event is moved to `DEAD_LETTER` and an alert is dispatched to the escalation subsystem.
