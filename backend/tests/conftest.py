"""Every test starts with independent simulated platform state."""
from copy import deepcopy
import pytest
from app.graph import tools

BASELINE = deepcopy(tools.SIMULATED_STATE)

@pytest.fixture(autouse=True)
def isolated_simulation(monkeypatch):
    tools.SIMULATED_STATE.clear()
    tools.SIMULATED_STATE.update(deepcopy(BASELINE))
    monkeypatch.setattr(tools.random, 'random', lambda: 1.0)
    yield
    tools.SIMULATED_STATE.clear()
    tools.SIMULATED_STATE.update(deepcopy(BASELINE))
