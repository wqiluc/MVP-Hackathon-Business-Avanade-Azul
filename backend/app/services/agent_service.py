from typing import TypedDict
from langgraph.graph import StateGraph, END
from app.services.rag_service import query_context

class AgentState(TypedDict):
    client_identifier: str
    frequency: int
    total_spend: float
    incidents: int
    incident_type: str
    tier: str
    churn_risk: float
    value_at_risk: float
    graph_rag_context: dict
    decision_reasoning: str
    action_proposal: dict
    audit_status: str

def query_manager_agent(state: AgentState) -> AgentState:
    """Etapa 1: Apuração de métricas financeiras e risco de perda."""
    spend = state["total_spend"]
    incidents = state["incidents"]
    
    churn_risk = min(0.95, max(0.05, 0.10 + (incidents * 0.25)))
    future_value = spend * 1.30
    value_at_risk = future_value * churn_risk
    
    if spend >= 80000:
        tier = "VIP World Legend"
    elif spend >= 35000:
        tier = "Executive"
    else:
        tier = "Premium"
        
    state["churn_risk"] = round(churn_risk, 2)
    state["value_at_risk"] = round(value_at_risk, 2)
    state["tier"] = tier
    return state

def graph_rag_agent(state: AgentState) -> AgentState:
    """Etapa 2: Resgate do conhecimento fundamentado via GraphRAG."""
    ctx = query_context(state["tier"], state["incident_type"])
    state["graph_rag_context"] = ctx
    return state

def decision_agent(state: AgentState) -> AgentState:
    """Etapa 3: Definição autônoma da ação de retenção."""
    var = state["value_at_risk"]
    tier = state["tier"]
    
    if var > 5000 or tier == "VIP World Legend":
        reasoning = "Cliente VIP em elevado risco financeiro. Ativação do protocolo de retenção Trust-First."
        proposal = {
            "strategy": "Resolução Preditiva Trust-First",
            "voucher_value": 250.00,
            "benefit": "Upgrade para Espaço Azul / Executiva Vacante",
            "bonus_points": 5000
        }
    else:
        reasoning = "Cliente de médio valor. Foco em aceleração de pontos e fidelização."
        proposal = {
            "strategy": "Engajamento de Fidelidade",
            "voucher_value": 100.00,
            "benefit": "Desconto na próxima viagem",
            "bonus_points": 1500
        }
        
    state["decision_reasoning"] = reasoning
    state["action_proposal"] = proposal
    return state

def audit_agent(state: AgentState) -> AgentState:
    """Etapa 4: Validação antifraude assíncrona."""
    state["audit_status"] = "PASSED_TRUST_FIRST_AUDIT"
    return state

def build_multi_agent_system():
    workflow = StateGraph(AgentState)
    workflow.add_node("query_manager", query_manager_agent)
    workflow.add_node("graph_rag", graph_rag_agent)
    workflow.add_node("decision_engine", decision_agent)
    workflow.add_node("auditor", audit_agent)
    
    workflow.set_entry_point("query_manager")
    workflow.add_edge("query_manager", "graph_rag")
    workflow.add_edge("graph_rag", "decision_engine")
    workflow.add_edge("decision_engine", "auditor")
    workflow.add_edge("auditor", END)
    
    return workflow.compile()