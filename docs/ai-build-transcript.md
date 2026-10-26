# AI Build Transcript

## Objective

This project was built with AI assistance as required by the engineering assessment.

AI was used as an implementation and design partner, while the final architecture, safety boundaries, and trade-offs were selected to match production agent-engineering requirements.

## How AI was used

### 1. Use-case selection

**Prompt used:**

> I need to build a 2-4 hour AI agent assessment for a platform engineering task. It must include planning, tool use, error recovery, human-in-the-loop, durable state, backend APIs, and an operator UI. Which use case gives the strongest demonstration without requiring cloud credentials?

**AI contribution:**

- Recommended incident triage as the strongest use case.
- Suggested separating read-only investigation tools from mutating remediation tools.
- Recommended a simulated environment so reviewers can run the project locally.

### 2. Architecture design

**Prompt used:**

> Design a LangGraph incident triage agent with durable state, resumability, human approval, context budgeting, observability, and a FastAPI/React UI. Avoid making it a chatbot wrapper.

**AI contribution:**

- Proposed a bounded planner-executor graph.
- Recommended workflow-oriented state rather than chat-message-only state.
- Recommended `interrupt()` for the approval boundary.
- Recommended SQLite for local development and PostgreSQL for production.

### 3. Implementation

**Prompt used:**

> Generate the backend graph, simulated tools, FastAPI endpoints, SSE event streaming, and React operator console. Include a transient tool failure and a retry path.

**AI contribution:**

- Generated the initial project structure.
- Implemented graph nodes, state, tools, API routes, and frontend components.
- Added a simulated telemetry failure to demonstrate retry and recovery.

### 4. Review and refinement

**Prompt used:**

> Review this assessment from the perspective of a senior AI platform engineer. What would make it look like genuine agent autonomy rather than a demo?

**AI contribution:**

- Emphasized explicit state over hidden chat history.
- Emphasized approval before mutation.
- Emphasized structured diagnosis and evidence.
- Emphasized operator visibility into reasoning, tool use, failures, and proposed actions.
- Recommended documenting trade-offs and future production improvements.

## Human decisions

The following decisions were made by the candidate:

- Selected incident triage over infra provisioning or deployment orchestration.
- Chose LangGraph for explicit control flow, checkpoints, and interrupts.
- Chose Python and FastAPI for the backend.
- Kept the first version focused rather than adding unnecessary multi-agent complexity.
- Made all investigation tools read-only.
- Required explicit human approval for every mutating action.
- Included an intentional transient failure to demonstrate recovery.
- Designed the UI around operator intervention rather than free-form chat.

## Assessment takeaway

AI accelerated scaffolding, implementation, documentation, and review. The important engineering work was defining the autonomy boundary, state model, failure behavior, safety controls, and operator experience.
