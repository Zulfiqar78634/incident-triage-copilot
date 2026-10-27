import pytest
from app.graph import nodes


def evidence_state():
    return {'alert': {'service': 'checkout-service'}, 'observations': [
        {'tool': 'get_service_health', 'result': {'service': 'payments-service', 'status': 'degraded'}},
        {'tool': 'query_logs', 'args': {'service': 'payments-service'}, 'result': {'matches': ['ERROR pool exhausted']}},
        {'tool': 'get_recent_deployments', 'result': {'deployments': [{'service': 'payments-service', 'version': 'new', 'previous_version': 'old'}]}}
    ]}


def test_unknown_previous_version_blocks_action():
    state = evidence_state()
    del state['observations'][-1]['result']['deployments'][0]['previous_version']
    assert nodes.observed_action(state) is None


def test_missing_error_evidence_blocks_action():
    state = evidence_state()
    state['observations'][1]['result']['matches'] = []
    assert nodes.observed_action(state) is None


@pytest.mark.asyncio
async def test_failed_verification_is_not_resolved(monkeypatch):
    state = evidence_state()
    state['proposed_action'] = nodes.observed_action(state)
    state['approval'] = {'decision': 'approve'}
    async def apply(**kwargs):
        return {'status': 'applied'}
    async def unhealthy(service):
        return {'status': 'degraded', 'error_rate': .2, 'p99_latency_ms': 2000}
    monkeypatch.setattr(nodes, 'apply_remediation', apply)
    monkeypatch.setattr(nodes, 'get_service_health', unhealthy)
    result = await nodes.execute_remediation(state)
    assert result['status'] == 'needs_human'


@pytest.mark.asyncio
async def test_retry_success_retains_failure():
    attempts = 0
    async def transient():
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise ConnectionError('temporary outage')
        return {'ok': True}
    result = await nodes._run_with_retry(transient, {})
    assert result['ok']
    assert len(result['attempts']) == 2
    assert not result['attempts'][0]['ok']


@pytest.mark.asyncio
async def test_fallback_diagnosis_does_not_invent_evidence(monkeypatch):
    async def no_model(*args):
        return None
    monkeypatch.setattr(nodes, 'model_call', no_model)
    result = await nodes.diagnose({'alert': {'service': 'checkout-service'}, 'observations': [], 'tool_errors': []})
    assert result['diagnosis']['evidence'] == []
    assert result['proposed_action'] is None
    assert result['status'] == 'needs_human'
