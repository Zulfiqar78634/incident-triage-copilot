# Architecture

## Runtime

The backend is a FastAPI service that owns the LangGraph agent runtime.

It exposes:

- Incident creation
- Agent event streaming
- Persisted state inspection
- Human approval and resume
- Run cancellation

## State machine

```text
classify_alert
      |
plan_investigation
      |
investigate
      |
diagnose
      |
request_approval -- reject --> END
      |
   approve
      |
execute_remediation
      |
     END
```

## State boundaries

The graph state contains:

- Alert and severity
- Investigation plan
- Completed steps
- Evidence and observations
- Tool errors and retry metadata
- Diagnosis and confidence
- Proposed remediation
- Operator approval
- Run status

This makes the agent resumable and auditable. Chat messages are only one part of the state; they do not replace workflow state.

## Tool boundary

Read-only tools:

- `get_service_health`
- `query_logs`
- `get_recent_deployments`
- `run_diagnostic`

Mutating tool:

- `apply_remediation`

The mutating tool is reachable only after `request_approval` returns an explicit `approve` decision.

## Persistence

LangGraph uses a SQLite checkpointer keyed by `thread_id`.

For this assessment, SQLite keeps the project easy to run locally. In production, the same design should use PostgreSQL or another externally durable checkpointer so that multiple API workers can safely resume the same incident.

## Observability

The API streams structured events for:

- Agent reasoning
- Plan updates
- Tool invocation and completion
- Tool failure and retry
- Diagnosis
- Approval requests
- State transitions

A production version would additionally export OpenTelemetry GenAI spans for LLM calls, tool calls, graph transitions, token usage, latency, and cost.
