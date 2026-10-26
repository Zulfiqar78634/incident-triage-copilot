"""API regression tests with temporary durable state and deterministic telemetry."""
import time
from fastapi.testclient import TestClient
import pytest
from app import main
from app.graph import tools

@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(main, 'DATABASE_PATH', str(tmp_path / 'incidents.db'))
    monkeypatch.setattr(tools.random, 'random', lambda: 1.0)
    import app.llm as llm
    monkeypatch.setattr(llm, 'LLM_MODE', 'mock')
    with TestClient(main.app) as instance:
        yield instance

def wait_approval(client, incident_id):
    for _ in range(100):
        response = client.get(f'/api/incidents/{incident_id}/state')
        assert response.status_code == 200, response.text
        result = response.json()
        if result['interrupted']:
            return result
        assert result['state']['status'] != 'failed', result
        time.sleep(0.05)
    pytest.fail('Approval checkpoint was not reached')

def test_reject_preserves_no_mutation(client):
    before = len(tools.SIMULATED_STATE['remediation_history'])
    response = client.post('/api/incidents', json={'scenario': 'checkout_latency'})
    assert response.status_code == 200, response.text
    incident_id = response.json()['incident_id']
    result = wait_approval(client, incident_id)
    assert result['state']['observations']
    rejected = client.post(f'/api/incidents/{incident_id}/resume', json={'decision': 'reject'})
    assert rejected.status_code == 200, rejected.text
    assert rejected.json()['state']['status'] == 'needs_human'
    assert len(tools.SIMULATED_STATE['remediation_history']) == before
    assert client.post(f'/api/incidents/{incident_id}/resume', json={'decision': 'approve'}).status_code == 409

def test_approve_resolves(client):
    response = client.post('/api/incidents', json={})
    assert response.status_code == 200, response.text
    incident_id = response.json()['incident_id']
    wait_approval(client, incident_id)
    approved = client.post(f'/api/incidents/{incident_id}/resume', json={'decision': 'approve', 'operator_note': 'Test approval'})
    assert approved.status_code == 200, approved.text
    assert approved.json()['state']['status'] == 'resolved'
    assert approved.json()['state']['observations'][-1]['result']['status'] == 'healthy'

def test_invalid_inputs(client):
    assert client.get('/api/incidents/missing/state').status_code == 404
    assert client.post('/api/incidents', json={'scenario': 'unknown'}).status_code == 422
    assert client.post('/api/incidents/missing/resume', json={'decision': 'edit'}).status_code == 422
