"""FastAPI entrypoint for the agent runtime."""

import asyncio
import json
import uuid
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from langgraph.types import Command

from app.graph.build import graph
from app.graph.state import initial_state

app = FastAPI(title="Incident Triage Copilot", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

SCENARIOS = {
    "checkout_latency": {
        "title": "Checkout latency and error-rate spike",
        "service": "checkout-service",
        "error_rate": 0.18,
        "p99_latency_ms": 2450,
    }
}


class StartIncidentRequest(BaseModel):
    scenario: str = "checkout_latency"


class ResumeRequest(BaseModel):
    decision: str
    operator_note: str | None = None
    edited_action: dict[str, Any] | None = None


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/api/incidents")
async def start_incident(request: StartIncidentRequest):
    incident_id = str(uuid.uuid4())
    alert = SCENARIOS.get(request.scenario, SCENARIOS["checkout_latency"])
    state = initial_state(incident_id, request.scenario, alert)

    config = {"configurable": {"thread_id": incident_id}}
    graph.update_state(config, state)

    return {
        "incident_id": incident_id,
        "scenario": request.scenario,
        "state": graph.get_state(config).values,
    }


@app.get("/api/incidents/{incident_id}/state")
async def get_state(incident_id: str):
    config = {"configurable": {"thread_id": incident_id}}
    snapshot = graph.get_state(config)

    return {
        "incident_id": incident_id,
        "state": snapshot.values,
        "next": snapshot.next,
        "interrupted": bool(snapshot.next),
    }


@app.get("/api/incidents/{incident_id}/events")
async def stream_events(incident_id: str):
    async def event_stream():
        config = {"configurable": {"thread_id": incident_id}}
        snapshot = graph.get_state(config)

        # Start the graph on the first event connection. If the graph is
        # already interrupted, do not restart it; wait for an operator resume.
        input_value = snapshot.values if not snapshot.next else None

        async for mode, chunk in graph.astream(
            input_value,
            config=config,
            stream_mode=["updates", "values"],
        ):
            payload = {
                "mode": mode,
                "data": chunk if isinstance(chunk, dict) else str(chunk),
            }
            yield f"data: {json.dumps(payload, default=str)}\n\n"
            await asyncio.sleep(0.01)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
    )


@app.post("/api/incidents/{incident_id}/resume")
async def resume_incident(incident_id: str, request: ResumeRequest):
    decision = {
        "decision": request.decision,
        "operator_note": request.operator_note,
        "edited_action": request.edited_action,
    }

    config = {"configurable": {"thread_id": incident_id}}
    result = graph.invoke(
        Command(resume=decision),
        config=config,
    )

    return {
        "incident_id": incident_id,
        "status": result.get("status"),
        "state": graph.get_state(config).values,
    }


@app.post("/api/incidents/{incident_id}/cancel")
async def cancel_incident(incident_id: str):
    config = {"configurable": {"thread_id": incident_id}}
    graph.update_state(config, {"status": "cancelled"})

    return {
        "incident_id": incident_id,
        "status": "cancelled",
    }
