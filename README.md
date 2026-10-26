# Incident Triage Copilot

An operator-in-the-loop AI agent for production incident triage.

The agent investigates a simulated production incident, correlates telemetry and deployment evidence, proposes a remediation, pauses for explicit operator approval, executes the approved action, and verifies recovery.

It is designed to demonstrate the engineering concerns behind production agent systems:

- Planning and multi-step tool use
- Durable, resumable execution
- Human-in-the-loop approval
- Error recovery and bounded retries
- Context budgeting and compaction
- Structured observability
- Safe tool boundaries

## Use case

A network operations engineer receives an alert:

> `checkout-service` p99 latency has increased by 340% and its error rate is 18%.

The agent:

1. Classifies the alert.
2. Creates an investigation plan.
3. Queries service health, logs, recent deployments, and dependency diagnostics.
4. Handles a simulated transient telemetry failure.
5. Identifies the likely root cause.
6. Proposes a rollback with evidence, confidence, blast radius, and risk.
7. Waits for operator approval.
8. Executes the approved rollback.
9. Verifies recovery and produces an incident summary.

The mutating remediation tool is intentionally separated from all read-only investigation tools.

## Architecture

```text
React Operator Console
        |
        | SSE + REST
        v
FastAPI Agent Runtime
        |
        v
LangGraph State Machine
        |
        +-- classify_alert
        +-- plan_investigation
        +-- investigate
        +-- diagnose
        +-- request_approval  <-- interrupt()
        +-- execute_remediation
        |
        v
SQLite Checkpointer + Simulated Platform Tools
```

The agent state is checkpointed by `thread_id`. An incident can be inspected, resumed after a browser refresh, or continued after a backend restart.

## Agent design

The agent uses a bounded planner-executor pattern rather than an unconstrained agent loop.

- The planner creates an explicit investigation plan.
- The executor selects read-only tools based on the current state.
- Tool failures are recorded in state and retried with backoff.
- The diagnosis is structured JSON, not free-form text.
- Remediation requires an explicit human decision.
- Every meaningful transition emits an observable event.

This keeps autonomy useful while making unsafe paths explicit and testable.

## Context engineering

The runtime applies a simple context budget:

- System policy and incident summary are always retained.
- Tool outputs are truncated before entering model context.
- Only evidence-bearing log lines are retained.
- Older observations are summarized when the working context exceeds its budget.
- The current plan, hypotheses, failed tools, and approval state remain explicit graph state rather than being buried in chat history.

## Local setup

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --port 8000
```

Set your model provider credentials in `backend/.env`.

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Open:

```text
http://localhost:5173
```

## API

### Start an incident

```http
POST /api/incidents
{
  "scenario": "checkout_latency"
}
```

### Stream agent events

```http
GET /api/incidents/{incident_id}/events
```

Event types include:

- `agent_thought`
- `plan_updated`
- `tool_started`
- `tool_result`
- `tool_error`
- `diagnosis_ready`
- `approval_required`
- `state_updated`
- `run_finished`

### Inspect persisted state

```http
GET /api/incidents/{incident_id}/state
```

### Approve, reject, or edit remediation

```http
POST /api/incidents/{incident_id}/resume
{
  "decision": "approve",
  "operator_note": "Approved. No active payment processing window."
}
```

### Cancel a run

```http
POST /api/incidents/{incident_id}/cancel
```

## Safety model

| Action type | Agent permission |
|---|---|
| Read telemetry | Autonomous |
| Read logs | Autonomous |
| Read deployments | Autonomous |
| Run diagnostics | Autonomous |
| Restart service | Approval required |
| Roll back deployment | Approval required |
| Change configuration | Approval required |

The agent cannot call a mutating tool until `request_approval` has received an explicit operator decision.

## What is next

- Replace simulated tools with Kubernetes, GitHub, PagerDuty, and observability integrations.
- Move from SQLite to PostgreSQL for multi-worker durable execution.
- Add policy-based auto-approval for low-risk, reversible actions.
- Add prompt-injection regression tests and sandboxed tool execution.
- Add offline evaluation scenarios and LLM-as-judge scoring.
- Add OpenTelemetry GenAI-compatible tracing and cost dashboards.
