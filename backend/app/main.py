"""Single-worker prototype runtime. Event reads never execute the graph."""
import asyncio
import json
import logging
import uuid
from contextlib import asynccontextmanager
from typing import Literal
from fastapi import FastAPI, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.types import Command
from pydantic import BaseModel, ConfigDict
from app.config import DATABASE_PATH
from app.graph.build import build_graph
from app.graph.state import initial_state

logger = logging.getLogger(__name__)
TERMINAL = {'resolved', 'failed', 'cancelled', 'needs_human'}
ALERT = {'title': 'Checkout latency and error-rate spike', 'service': 'checkout-service', 'error_rate': 0.18, 'p99_latency_ms': 2450}

@asynccontextmanager
async def lifespan(app):
    app.state.tasks = {}
    async with AsyncSqliteSaver.from_conn_string(DATABASE_PATH) as saver:
        await saver.setup()
        app.state.graph = build_graph(saver)
        try:
            yield
        finally:
            tasks = list(app.state.tasks.values())
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)

app = FastAPI(title='Incident Triage Copilot', lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=['http://localhost:5173', 'http://127.0.0.1:5173'], allow_methods=['*'], allow_headers=['*'])

class StartRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    scenario: Literal['checkout_latency'] = 'checkout_latency'

class DecisionRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    decision: Literal['approve', 'reject']
    operator_note: str | None = None


def config(incident_id):
    return {'configurable': {'thread_id': incident_id}}

async def snapshot(request, incident_id):
    result = await request.app.state.graph.aget_state(config(incident_id))
    if not result.values:
        raise HTTPException(404, 'Incident not found')
    return result

def response_for(incident_id, result):
    interrupted = any(getattr(task, 'interrupts', ()) for task in result.tasks)
    return jsonable_encoder({'incident_id': incident_id, 'state': result.values, 'next': list(result.next), 'interrupted': interrupted})

async def execute(app, incident_id, value):
    try:
        await app.state.graph.ainvoke(value, config=config(incident_id))
    except asyncio.CancelledError:
        raise
    except Exception:
        logger.exception('Incident execution failed: %s', incident_id)
        await app.state.graph.aupdate_state(config(incident_id), {'status': 'failed'})


def schedule(app, incident_id, value):
    existing = app.state.tasks.get(incident_id)
    if existing and not existing.done():
        raise HTTPException(409, 'Incident already executing')
    task = asyncio.create_task(execute(app, incident_id, value))
    app.state.tasks[incident_id] = task
    def cleanup(completed):
        if app.state.tasks.get(incident_id) is completed:
            app.state.tasks.pop(incident_id, None)
    task.add_done_callback(cleanup)

@app.get('/health')
async def health():
    return {'status': 'ok', 'environment': 'simulation', 'worker_mode': 'single'}

@app.post('/api/incidents')
async def start(body: StartRequest, request: Request):
    incident_id = str(uuid.uuid4())
    state = initial_state(incident_id, body.scenario, dict(ALERT))
    await request.app.state.graph.aupdate_state(config(incident_id), state, as_node='__start__')
    result = await snapshot(request, incident_id)
    schedule(request.app, incident_id, None)
    return response_for(incident_id, result)

@app.get('/api/incidents/{incident_id}/state')
async def state(incident_id: str, request: Request):
    return response_for(incident_id, await snapshot(request, incident_id))

@app.get('/api/incidents/{incident_id}/events')
async def events(incident_id: str, request: Request):
    await snapshot(request, incident_id)
    async def stream():
        previous = None
        while not await request.is_disconnected():
            result = await snapshot(request, incident_id)
            data = response_for(incident_id, result)
            serialized = json.dumps(data, sort_keys=True)
            if serialized != previous:
                payload = {'mode': 'values', 'data': data['state']}
                if data['interrupted']:
                    payload['data'] = dict(data['state'], __interrupt__=True)
                yield 'data: ' + json.dumps(payload) + '\n\n'
                previous = serialized
            if data['interrupted'] or data['state'].get('status') in TERMINAL:
                return
            yield ': heartbeat\n\n'
            await asyncio.sleep(0.25)
    return StreamingResponse(stream(), media_type='text/event-stream', headers={'Cache-Control': 'no-cache'})

@app.post('/api/incidents/{incident_id}/resume')
async def resume(incident_id: str, body: DecisionRequest, request: Request):
    result = await snapshot(request, incident_id)
    if result.values.get('status') in TERMINAL:
        raise HTTPException(409, 'Incident is terminal')
    existing = request.app.state.tasks.get(incident_id)
    if existing and not existing.done():
        raise HTTPException(409, 'Incident already executing')
    interrupted = any(getattr(task, 'interrupts', ()) for task in result.tasks)
    if not interrupted:
        raise HTTPException(409, 'No pending approval checkpoint')
    schedule(request.app, incident_id, Command(resume=body.model_dump()))
    task = request.app.state.tasks[incident_id]
    await asyncio.shield(task)
    return response_for(incident_id, await snapshot(request, incident_id))

@app.post('/api/incidents/{incident_id}/continue')
async def continue_run(incident_id: str, request: Request):
    result = await snapshot(request, incident_id)
    if any(getattr(task, 'interrupts', ()) for task in result.tasks):
        raise HTTPException(409, 'Use approval endpoint for interrupted runs')
    if result.values.get('status') in TERMINAL or not result.next:
        raise HTTPException(409, 'No recoverable work')
    schedule(request.app, incident_id, None)
    return {'incident_id': incident_id, 'status': 'scheduled'}

@app.post('/api/incidents/{incident_id}/cancel')
async def cancel(incident_id: str, request: Request):
    result = await snapshot(request, incident_id)
    if result.values.get('status') in TERMINAL:
        raise HTTPException(409, 'Incident is terminal')
    task = request.app.state.tasks.get(incident_id)
    if task and not task.done():
        raise HTTPException(409, 'Cancellation of active side effects is not supported; wait for approval checkpoint')
    await request.app.state.graph.aupdate_state(config(incident_id), {'status': 'cancelled'})
    return response_for(incident_id, await snapshot(request, incident_id))
