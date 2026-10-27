import pytest
from app.graph.build import configure_simulation, route_diagnosis, route
from app.graph import nodes, tools


def test_no_candidate_escalates_without_approval():
    assert route_diagnosis({'proposed_action': None}) == 'mark_rejected'
    assert route({'approval': {'decision': 'reject'}}) == 'mark_rejected'


def test_candidate_goes_to_operator():
    assert route_diagnosis({'proposed_action': {'action_type': 'rollback'}}) == 'mark_awaiting'


def test_previous_version_is_explicit_fixture_metadata():
    configure_simulation()
    deployment = next(d for d in tools.SIMULATED_STATE['deployments'] if d['service'] == 'payments-service')
    assert deployment['previous_version'] == 'v2.13.2'
    assert deployment['metadata_source'] == 'explicit simulated deployment fixture'


@pytest.mark.asyncio
async def test_collected_evidence_supports_known_simulated_target(monkeypatch):
    configure_simulation()
    async def no_model(*args):
        return None
    monkeypatch.setattr(nodes, 'model_call', no_model)
    state = {'alert': {'service': 'checkout-service'}, 'observations': [], 'tool_errors': []}
    state.update(await nodes.investigate(state))
    result = await nodes.diagnose(state)
    assert result['proposed_action']['service'] == 'payments-service'
    assert result['proposed_action']['target_version'] == 'v2.13.2'
    assert result['proposed_action']['requires_approval'] is True
    assert result['diagnosis']['rollback_safe'] is False


@pytest.mark.asyncio
async def test_missing_metadata_does_not_guess_rollback(monkeypatch):
    async def no_model(*args):
        return None
    monkeypatch.setattr(nodes, 'model_call', no_model)
    for deployment in tools.SIMULATED_STATE['deployments']:
        deployment.pop('previous_version', None)
    state = {'alert': {'service': 'checkout-service'}, 'observations': [], 'tool_errors': []}
    state.update(await nodes.investigate(state))
    result = await nodes.diagnose(state)
    assert result['proposed_action'] is None
    assert result['status'] == 'needs_human'
