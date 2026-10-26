"""Builds and compiles the incident triage graph."""

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, StateGraph
from langgraph.types import Command

from app.config import DATABASE_PATH
from app.graph.nodes import (
    classify_alert,
    diagnose,
    execute_remediation,
    investigate,
    plan_investigation,
    request_approval,
)
from app.graph.state import IncidentState


def _route_after_approval(state: IncidentState) -> str:
    approval = state.get("approval") or {}
    return "execute_remediation" if approval.get("decision") == "approve" else END


def build_graph():
    builder = StateGraph(IncidentState)

    builder.add_node("classify_alert", classify_alert)
    builder.add_node("plan_investigation", plan_investigation)
    builder.add_node("investigate", investigate)
    builder.add_node("diagnose", diagnose)
    builder.add_node("request_approval", request_approval)
    builder.add_node("execute_remediation", execute_remediation)

    builder.set_entry_point("classify_alert")
    builder.add_edge("classify_alert", "plan_investigation")
    builder.add_edge("plan_investigation", "investigate")
    builder.add_edge("investigate", "diagnose")
    builder.add_edge("diagnose", "request_approval")
    builder.add_conditional_edges("request_approval", _route_after_approval)
    builder.add_edge("execute_remediation", END)

    checkpointer = SqliteSaver.from_conn_string(DATABASE_PATH)
    return builder.compile(checkpointer=checkpointer)


graph = build_graph()


def resume_graph(thread_id: str, decision: dict):
    return graph.invoke(
        Command(resume=decision),
        config={"configurable": {"thread_id": thread_id}},
    )
