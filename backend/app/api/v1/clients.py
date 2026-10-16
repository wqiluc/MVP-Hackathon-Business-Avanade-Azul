from fastapi import APIRouter, Depends
from app.schemas.client_schema import ClientAnalysisRequest, ClientAnalysisResponse
from app.core.security import get_current_user, anonymize_identifier
from app.services.agent_service import build_multi_agent_system

router = APIRouter()
agent_orchestrator = build_multi_agent_system()

@router.post("/analyze", response_model=ClientAnalysisResponse)
def analyze_client(req: ClientAnalysisRequest, current_user: dict = Depends(get_current_user)):
    anon_id = anonymize_identifier(req.raw_user_id)
    
    initial_state = {
        "client_identifier": anon_id,
        "frequency": req.frequency,
        "total_spend": req.total_spend,
        "incidents": req.incidents,
        "incident_type": req.incident_type,
        "tier": "",
        "churn_risk": 0.0,
        "value_at_risk": 0.0,
        "graph_rag_context": {},
        "decision_reasoning": "",
        "action_proposal": {},
        "audit_status": ""
    }
    
    final_state = agent_orchestrator.invoke(initial_state)
    
    return ClientAnalysisResponse(
        audience="Equipe Interna da Azul",
        client_identifier=final_state["client_identifier"],
        metrics={
            "tier": final_state["tier"],
            "churn_risk": final_state["churn_risk"],
            "value_at_risk": final_state["value_at_risk"]
        },
        graph_rag_context=final_state["graph_rag_context"],
        reasoning=final_state["decision_reasoning"],
        action_proposal=final_state["action_proposal"],
        audit_status=final_state["audit_status"]
    )