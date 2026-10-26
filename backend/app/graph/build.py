"""Graph construction; persistence is owned by the API lifespan."""
from langgraph.graph import END, StateGraph
from app.graph.nodes import classify_alert, plan_investigation, investigate, diagnose, request_approval, execute_remediation
from app.graph.state import IncidentState

async def mark_awaiting(state):
    return {'status': 'awaiting_approval'}

async def mark_rejected(state):
    return {'status': 'needs_human'}

def route(state):
    return 'execute_remediation' if (state.get('approval') or {}).get('decision') == 'approve' else 'mark_rejected'

def build_graph(checkpointer):
    builder = StateGraph(IncidentState)
    for name, node in [('classify_alert', classify_alert), ('plan_investigation', plan_investigation), ('investigate', investigate), ('diagnose', diagnose), ('mark_awaiting', mark_awaiting), ('request_approval', request_approval), ('mark_rejected', mark_rejected), ('execute_remediation', execute_remediation)]:
        builder.add_node(name, node)
    builder.set_entry_point('classify_alert')
    chain = ['classify_alert', 'plan_investigation', 'investigate', 'diagnose', 'mark_awaiting', 'request_approval']
    for left, right in zip(chain, chain[1:]):
        builder.add_edge(left, right)
    builder.add_conditional_edges('request_approval', route)
    builder.add_edge('mark_rejected', END)
    builder.add_edge('execute_remediation', END)
    return builder.compile(checkpointer=checkpointer)
