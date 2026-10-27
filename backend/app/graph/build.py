"""Graph construction; persistence is owned by the API lifespan.

The default tools are simulation-only. Previous-version metadata below is
explicit fixture data, not inferred production deployment history.
"""
from langgraph.graph import END, StateGraph
from app.graph.nodes import classify_alert, plan_investigation, investigate, diagnose, request_approval, execute_remediation
from app.graph.state import IncidentState
from app.graph.tools import SIMULATED_STATE

# Explicit default scenario metadata. Real integrations must obtain this from
# their deployment system and validate compatibility before offering rollback.
SIMULATED_PREVIOUS_VERSIONS = {('payments-service', 'v2.14.0'): 'v2.13.2'}

def configure_simulation():
    for deployment in SIMULATED_STATE['deployments']:
        key = (deployment['service'], deployment['version'])
        if key in SIMULATED_PREVIOUS_VERSIONS:
            deployment.setdefault('previous_version', SIMULATED_PREVIOUS_VERSIONS[key])
            deployment.setdefault('metadata_source', 'explicit simulated deployment fixture')

async def mark_awaiting(state):
    return {'status': 'awaiting_approval'}

async def mark_rejected(state):
    return {'status': 'needs_human'}

def route(state):
    return 'execute_remediation' if (state.get('approval') or {}).get('decision') == 'approve' else 'mark_rejected'

def route_diagnosis(state):
    return 'mark_awaiting' if state.get('proposed_action') else 'mark_rejected'

def build_graph(checkpointer):
    configure_simulation()
    builder = StateGraph(IncidentState)
    for name, node in [('classify_alert', classify_alert), ('plan_investigation', plan_investigation), ('investigate', investigate), ('diagnose', diagnose), ('mark_awaiting', mark_awaiting), ('request_approval', request_approval), ('mark_rejected', mark_rejected), ('execute_remediation', execute_remediation)]:
        builder.add_node(name, node)
    builder.set_entry_point('classify_alert')
    chain = ['classify_alert', 'plan_investigation', 'investigate', 'diagnose']
    for left, right in zip(chain, chain[1:]):
        builder.add_edge(left, right)
    builder.add_conditional_edges('diagnose', route_diagnosis)
    builder.add_edge('mark_awaiting', 'request_approval')
    builder.add_conditional_edges('request_approval', route)
    builder.add_edge('mark_rejected', END)
    builder.add_edge('execute_remediation', END)
    return builder.compile(checkpointer=checkpointer)
