"""Incident workflow state.

The state is intentionally workflow-oriented rather than chat-only.
"""

from typing import Annotated, Any, Literal, Optional

from typing_extensions import TypedDict
from langgraph.graph.message import add_messages


class IncidentState(TypedDict):
    messages: Annotated[list, add_messages]

    incident_id: str
    scenario: str
    alert: dict
    severity: Literal["low", "medium", "high", "critical"]

    plan: list[dict]
    completed_steps: list[str]

    observations: list[dict]
    hypotheses: list[dict]
    tool_errors: list[dict]
    retry_count: int

    diagnosis: Optional[dict]
    proposed_action: Optional[dict]
    approval: Optional[dict]

    context_summary: str
    status: Literal[
        "created",
        "investigating",
        "awaiting_approval",
        "remediating",
        "resolved",
        "needs_human",
        "cancelled",
        "failed",
    ]


def initial_state(incident_id: str, scenario: str, alert: dict) -> dict[str, Any]:
    return {
        "messages": [],
        "incident_id": incident_id,
        "scenario": scenario,
        "alert": alert,
        "severity": "medium",
        "plan": [],
        "completed_steps": [],
        "observations": [],
        "hypotheses": [],
        "tool_errors": [],
        "retry_count": 0,
        "diagnosis": None,
        "proposed_action": None,
        "approval": None,
        "context_summary": "",
        "status": "created",
    }
