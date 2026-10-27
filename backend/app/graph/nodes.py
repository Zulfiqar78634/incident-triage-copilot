"""Bounded investigation prototype. Planning remains deterministic, not model-driven."""
import asyncio
import json
import time
from langgraph.types import interrupt
from app.config import MAX_TOOL_CALLS
from app.graph.tools import apply_remediation, get_recent_deployments, get_service_health, query_logs, run_diagnostic
from app.llm import classify_with_gemini, diagnose_with_gemini

async def model_call(function, *args):
    # Timeout bounds waiting; an already running SDK thread cannot be forcibly stopped.
    return await asyncio.wait_for(asyncio.to_thread(function, *args), timeout=45)

async def classify_alert(state):
    result = await model_call(classify_with_gemini, state['alert'])
    severity = result['severity'] if result else ('critical' if state['alert'].get('error_rate', 0) >= .2 else 'high')
    return {'severity': severity, 'status': 'investigating', 'messages': [{'role': 'assistant', 'content': f'Incident classified as {severity}.'}]}

async def plan_investigation(state):
    return {'plan': [{'id': key, 'description': description, 'status': 'pending'} for key, description in [('health', 'Inspect affected service health'), ('logs', 'Inspect affected service errors'), ('dependency_health', 'Inspect unhealthy dependency'), ('deployments', 'Inspect dependency deployments'), ('dependency_logs', 'Inspect dependency errors')]], 'completed_steps': []}

async def _run_with_retry(tool, args, max_retries=1):
    attempts = []
    for attempt in range(max_retries + 1):
        started = time.monotonic()
        try:
            result = await asyncio.wait_for(tool(**args), timeout=10)
            attempts.append({'attempt': attempt + 1, 'ok': True, 'duration_ms': round((time.monotonic() - started) * 1000)})
            return {'ok': True, 'result': result, 'attempts': attempts}
        except (ConnectionError, TimeoutError) as exc:
            attempts.append({'attempt': attempt + 1, 'ok': False, 'error': str(exc) or type(exc).__name__})
            if attempt < max_retries:
                await asyncio.sleep(.2 * 2 ** attempt)
        except Exception as exc:
            attempts.append({'attempt': attempt + 1, 'ok': False, 'error': str(exc)})
            break
    return {'ok': False, 'result': None, 'attempts': attempts}

async def investigate(state):
    service = state['alert']['service']
    observations = []
    errors = []
    completed = []
    async def collect(step, tool, args):
        if len(observations) + len(errors) >= MAX_TOOL_CALLS:
            return None
        outcome = await _run_with_retry(tool, args)
        item = {'id': f'E{len(observations) + 1}', 'step': step, 'tool': tool.__name__, 'args': args, 'attempts': outcome['attempts'], 'result': outcome['result']}
        if outcome['ok']:
            observations.append(item)
            completed.append(step)
        else:
            errors.append(item)
        return outcome['result']
    health = await collect('health', get_service_health, {'service': service})
    await collect('logs', query_logs, {'service': service, 'query': 'error'})
    dependencies = (health or {}).get('dependencies', {})
    target = next((name for name, status in dependencies.items() if status != 'healthy'), service)
    await collect('dependency_health', get_service_health, {'service': target})
    await collect('deployments', get_recent_deployments, {'service': target})
    await collect('dependency_logs', query_logs, {'service': target, 'query': 'error'})
    return {'observations': observations, 'tool_errors': errors, 'completed_steps': completed}


def observed_action(state):
    observations = state.get('observations', [])
    health = [o['result'] for o in observations if o.get('tool') == 'get_service_health' and isinstance(o.get('result'), dict)]
    deployments = [d for o in observations if o.get('tool') == 'get_recent_deployments' and isinstance(o.get('result'), dict) for d in o['result'].get('deployments', [])]
    for deployment in deployments:
        service = deployment.get('service')
        degraded = any(h.get('service') == service and h.get('status') == 'degraded' for h in health)
        error_logs = any(o.get('tool') == 'query_logs' and o.get('args', {}).get('service') == service and (o.get('result') or {}).get('matches') for o in observations)
        previous = deployment.get('previous_version')
        if degraded and error_logs and previous:
            return {'action_type': 'rollback', 'service': service, 'target_version': previous, 'reason': 'Observed degraded service, error logs, and deployment with known previous version; causal relationship remains a hypothesis.', 'risk': 'requires operator assessment', 'requires_approval': True}
    return None

async def diagnose(state):
    observations = state.get('observations', [])
    evidence = [f"{o.get('id', 'Evidence')}: {o['tool']}({json.dumps(o.get('args', {}))}) returned {json.dumps(o.get('result'))}" for o in observations]
    generated = await model_call(diagnose_with_gemini, state['alert'], observations, state.get('tool_errors', []))
    diagnosis = generated or {'root_cause': 'Root cause not established; operator review required.', 'confidence': 0.0, 'evidence': evidence, 'blast_radius': state['alert']['service'], 'rollback_safe': False}
    action = observed_action(state)
    # Model narrative cannot create executable actions or assert rollback safety.
    diagnosis = dict(diagnosis, rollback_safe=False)
    return {'diagnosis': diagnosis, 'proposed_action': action, 'context_summary': f'{len(observations)} observations collected. ' + ('A candidate action requires review.' if action else 'No supported rollback target; escalate without mutation.'), 'status': 'investigating' if action else 'needs_human'}

async def request_approval(state):
    if not state.get('proposed_action'):
        return {'approval': {'decision': 'reject', 'operator_note': 'No evidence-supported action available'}, 'status': 'needs_human'}
    decision = interrupt({'type': 'approval_required', 'proposed_action': state['proposed_action'], 'diagnosis': state['diagnosis']})
    return {'approval': decision}


def recovered(health):
    return health.get('status') == 'healthy' and health.get('error_rate', 1) < .01 and health.get('p99_latency_ms', float('inf')) < 1000

async def execute_remediation(state):
    if (state.get('approval') or {}).get('decision') != 'approve':
        return {'status': 'needs_human'}
    action = state.get('proposed_action')
    if not action or action != observed_action(state):
        raise ValueError('Proposed action no longer matches validated observations')
    result = await asyncio.wait_for(apply_remediation(action_type=action['action_type'], service=action['service'], target_version=action['target_version'], reason=action['reason']), timeout=15)
    target = await asyncio.wait_for(get_service_health(action['service']), timeout=10)
    affected = await asyncio.wait_for(get_service_health(state['alert']['service']), timeout=10)
    ok = recovered(target) and recovered(affected)
    return {'status': 'resolved' if ok else 'needs_human', 'observations': state.get('observations', []) + [{'step': 'remediation', 'tool': 'apply_remediation', 'result': result}, {'step': 'verification', 'tool': 'get_service_health', 'result': target}, {'step': 'affected_service_verification', 'tool': 'get_service_health', 'result': affected}], 'messages': [{'role': 'assistant', 'content': 'Recovery criteria satisfied for target and affected service.' if ok else 'Action completed but recovery criteria failed; escalate to operator.'}]}
