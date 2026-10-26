"""LangGraph nodes for the incident triage workflow."""

import asyncio
import json
from typing import Any

from langgraph.types import interrupt

from app.config import MAX_TOOL_CALLS
from app.graph.tools import (
    apply_remediation,
    get_recent_deployments,
    get_service_health,
    query_logs,
    run_diagnostic,
)
from app.llm import classify_with_gemini, diagnose_with_gemini


async def classify_alert(state: dict[str, Any]) -> dict[str, Any]:
    alert = state["alert"]
    error_rate = alert.get("error_rate", 0)

    gemini_result = classify_with_gemini(alert)
    if gemini_result:
        severity = gemini_result["severity"]
        reason = gemini_result.get("reason", "Classified by Gemini.")
    else:
        severity = "critical" if error_rate >= 0.2 else "high"
        reason = "Classified using deterministic alert thresholds."

    return {
        "severity": severity,
        "status": "investigating",
        "messages": [
            {
                "role": "assistant",
                "content": f"Classified incident as {severity}: {reason}",
            }
        ],
    }


async def plan_investigation(state: dict[str, Any]) -> dict[str, Any]:
    plan = [
        {"id": "health", "description": "Check service and dependency health", "status": "pending"},
        {"id": "logs", "description": "Search recent error logs", "status": "pending"},
        {"id": "deployments", "description": "Check recent deployments", "status": "pending"},
        {"id": "diagnostics", "description": "Run targeted dependency diagnostics", "status": "pending"},
        {"id": "diagnosis", "description": "Correlate evidence and propose remediation", "status": "pending"},
    ]

    return {
        "plan": plan,
        "completed_steps": [],
        "messages": [
            {
                "role": "assistant",
                "content": "Created investigation plan: health, logs, deployments, diagnostics, diagnosis.",
            }
        ],
    }


async def _run_with_retry(tool, args: dict[str, Any], max_retries: int = 1):
    """Runs a tool with bounded retry/backoff and returns a structured result."""
    attempts = []

    for attempt in range(max_retries + 1):
        try:
            result = await tool(**args)
            return {
                "ok": True,
                "attempt": attempt + 1,
                "result": result,
                "attempts": attempts,
            }
        except Exception as exc:  # noqa: BLE001 - demo boundary converts errors to state
            attempts.append({"attempt": attempt + 1, "error": str(exc)})
            if attempt < max_retries:
                await asyncio.sleep(0.2 * (2**attempt))

    return {
        "ok": False,
        "attempt": max_retries + 1,
        "result": None,
        "attempts": attempts,
    }


def _truncate(value: Any, limit: int = 700) -> Any:
    text = json.dumps(value, default=str)
    if len(text) <= limit:
        return value
    return {"truncated": True, "preview": text[:limit] + "..."}


async def investigate(state: dict[str, Any]) -> dict[str, Any]:
    service = state["alert"].get("service", "checkout-service")
    observations = list(state.get("observations", []))
    tool_errors = list(state.get("tool_errors", []))
    completed = list(state.get("completed_steps", []))

    investigation_steps = [
        ("health", get_service_health, {"service": service}),
        ("logs", query_logs, {"service": service, "query": "error"}),
        ("deployments", get_recent_deployments, {"service": service}),
        ("diagnostics", run_diagnostic, {"service": service, "dependency": "payments-service"}),
    ]

    messages = []

    for step_id, tool, args in investigation_steps:
        if step_id in completed or len(completed) >= MAX_TOOL_CALLS:
            continue

        outcome = await _run_with_retry(tool, args)

        if outcome["ok"]:
            observations.append(
                {
                    "step": step_id,
                    "tool": tool.__name__,
                    "args": args,
                    "result": _truncate(outcome["result"]),
                }
            )
            completed.append(step_id)
            messages.append(
                {
                    "role": "assistant",
                    "content": f"Completed {step_id} investigation using {tool.__name__}.",
                }
            )
        else:
            tool_errors.append(
                {
                    "step": step_id,
                    "tool": tool.__name__,
                    "args": args,
                    "attempts": outcome["attempts"],
                }
            )
            messages.append(
                {
                    "role": "assistant",
                    "content": f"{step_id} investigation failed after retry; continuing with available evidence.",
                }
            )

    return {
        "observations": observations,
        "completed_steps": completed,
        "tool_errors": tool_errors,
        "messages": messages,
    }


async def diagnose(state: dict[str, Any]) -> dict[str, Any]:
    evidence = state.get("observations", [])
    errors = state.get("tool_errors", [])

    gemini_diagnosis = diagnose_with_gemini(
        state["alert"],
        evidence,
        errors,
    )

    if gemini_diagnosis:
        diagnosis = gemini_diagnosis
        diagnosis_source = "Gemini"
    else:
        diagnosis = {
            "root_cause": "Recent payments-service v2.14.0 deployment caused dependency timeouts and checkout failures.",
            "confidence": 0.86,
            "evidence": [
                "checkout-service reports payments-service timeouts",
                "payments-service was deployed 22 minutes before the alert",
                "payments-service logs show connection-pool exhaustion",
            ],
            "blast_radius": "checkout-service and payment processing",
            "rollback_safe": True,
        }
        diagnosis_source = "deterministic rules"

    proposed_action = {
        "action_type": "rollback",
        "service": "payments-service",
        "target_version": "v2.13.2",
        "reason": "Revert suspected regression introduced by v2.14.0",
        "risk": "low",
        "requires_approval": True,
    }

    summary = (
        f"Investigated {state['alert'].get('service')}. "
        f"Collected {len(evidence)} observations and encountered {len(errors)} tool failures. "
        f"Diagnosis generated using {diagnosis_source}."
    )

    return {
        "diagnosis": diagnosis,
        "proposed_action": proposed_action,
        "context_summary": summary,
        "messages": [
            {
                "role": "assistant",
                "content": summary,
            }
        ],
    }


async def request_approval(state: dict[str, Any]) -> dict[str, Any]:
    decision = interrupt(
        {
            "type": "approval_required",
            "diagnosis": state.get("diagnosis"),
            "proposed_action": state.get("proposed_action"),
            "question": "Approve the proposed remediation?",
        }
    )

    return {
        "approval": decision,
        "messages": [
            {
                "role": "assistant",
                "content": f"Operator decision received: {decision.get('decision')}",
            }
        ],
    }


async def execute_remediation(state: dict[str, Any]) -> dict[str, Any]:
    approval = state.get("approval") or {}

    if approval.get("decision") != "approve":
        return {
            "status": "needs_human",
            "messages": [
                {
                    "role": "assistant",
                    "content": "Remediation declined. Incident remains open for manual handling.",
                }
            ],
        }

    action = state.get("proposed_action") or {}
    result = await apply_remediation(
        action_type=action["action_type"],
        service=action["service"],
        target_version=action.get("target_version"),
        reason=action.get("reason", "Operator-approved remediation"),
    )

    verification = await get_service_health(action["service"])

    return {
        "status": "resolved",
        "observations": state.get("observations", [])
        + [
            {"step": "remediation", "tool": "apply_remediation", "result": result},
            {"step": "verification", "tool": "get_service_health", "result": verification},
        ],
        "messages": [
            {
                "role": "assistant",
                "content": (
                    f"Applied {action['action_type']} to {action['service']}. "
                    f"Post-remediation status: {verification.get('status')}"
                ),
            }
        ],
    }
