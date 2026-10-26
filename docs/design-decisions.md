# Design decisions

## Why incident triage?

Incident triage requires exactly the capabilities expected from a production agent:

- Understand an alert.
- Plan an investigation.
- Use multiple tools.
- Correlate partial or noisy evidence.
- Recover from tool failures.
- Recommend an action.
- Obtain human approval before changing production.
- Verify the result.

It also avoids turning the assessment into a generic chatbot demo.

## Why LangGraph?

LangGraph provides explicit control flow, graph-level state, checkpointing, interrupts, and resume semantics.

Those features matter because an incident agent must survive restarts, pause for approval, and expose a clear path from alert to remediation.

## Why not a single LLM call?

A single call can generate text, but it cannot reliably:

- Maintain investigation progress.
- Retry failed tools.
- Preserve evidence across steps.
- Pause for approval.
- Resume after a human decision.
- Separate diagnosis from execution.

## Why bounded autonomy?

The agent can independently investigate, but it cannot decide on its own to mutate production.

This creates a useful autonomy boundary:

- Investigation is autonomous.
- Diagnosis is autonomous.
- Remediation is human-gated.

## Why simulated tools?

The assessment focuses on agent runtime, state, safety, and operator UX. Simulated tools make the repository immediately runnable without cloud credentials while preserving realistic workflow behavior.

## Context strategy

Raw logs and tool payloads can quickly consume context and reduce reasoning quality.

The runtime truncates tool output, retains evidence-bearing observations, and keeps workflow facts in explicit state. In a longer-running implementation, older observations would be summarized into `context_summary` while preserving the current diagnosis, plan, and approval state.

## Error recovery

The log-search tool intentionally fails intermittently.

The agent retries with exponential backoff, records the failure in state, and continues with available evidence instead of crashing or silently hiding the issue.

## Operator UX

The UI is designed for an operator, not a chat user.

It shows:

- What the agent is doing.
- What evidence it has found.
- What it proposes to do.
- What the risk and blast radius are.
- Exactly what requires approval.

The operator can approve, reject, add context, refresh persisted state, and observe the timeline.
