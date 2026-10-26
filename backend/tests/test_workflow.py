from app.graph.build import graph
from app.graph.state import initial_state


def test_graph_has_expected_nodes():
    expected = {
        "classify_alert",
        "plan_investigation",
        "investigate",
        "diagnose",
        "request_approval",
        "execute_remediation",
    }
    assert expected.issubset(set(graph.get_graph().nodes))


def test_initial_state_is_workflow_oriented():
    state = initial_state(
        "incident-1",
        "checkout_latency",
        {"service": "checkout-service", "error_rate": 0.18},
    )

    assert state["incident_id"] == "incident-1"
    assert state["status"] == "created"
    assert state["plan"] == []
    assert state["observations"] == []
    assert state["approval"] is None
