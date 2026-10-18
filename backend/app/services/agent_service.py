from ai.agents.workflow import (
    AgentState,
    audit_agent,
    build_multi_agent_system,
    decision_agent,
    graph_rag_agent,
    invoke_agent_workflow,
    query_manager_agent,
)
from app.core.security import anonymize_identifier


def analyze_client(
    raw_user_id: str,
    frequency: int,
    total_spend: float,
    incidents: int,
    incident_type: str,
) -> AgentState:
    state: AgentState = {
        "client_identifier": anonymize_identifier(raw_user_id),
        "frequency": frequency,
        "total_spend": total_spend,
        "incidents": incidents,
        "incident_type": incident_type,
        "tier": "",
        "churn_risk": 0.0,
        "value_at_risk": 0.0,
        "graph_rag_context": {},
        "decision_reasoning": "",
        "action_proposal": {},
        "audit_status": "",
    }
    return invoke_agent_workflow(state)
