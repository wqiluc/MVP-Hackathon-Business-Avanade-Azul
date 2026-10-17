from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from app.schemas.client_schema import ClientAnalysisRequest, ClientAnalysisResponse
from app.services.crm_service import CrmService, gerar_recomendacao
from app.core.security import get_current_user, anonymize_identifier
from app.services.agent_service import invoke_agent_workflow

router = APIRouter()

@router.post("/analyze-client", include_in_schema=False)
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
    
    final_state = invoke_agent_workflow(initial_state)
    
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

@router.get("")
@router.get("/")
def listar_clientes(persona: Optional[str] = None, tier: Optional[str] = None,
                    current_user: dict = Depends(get_current_user)):
    return CrmService.listar(persona, tier)


@router.get("/{cliente_id}")
def obter_cliente(cliente_id: str, current_user: dict = Depends(get_current_user)):
    cliente = CrmService.obter(cliente_id)
    if not cliente:
        raise HTTPException(status_code=404, detail="Cliente não encontrado.")
    return cliente


@router.post("/{cliente_id}/recomendacao")
def recomendar(cliente_id: str, current_user: dict = Depends(get_current_user)):
    cliente = CrmService.obter(cliente_id)
    if not cliente:
        raise HTTPException(status_code=404, detail="Cliente não encontrado.")
    return gerar_recomendacao(cliente)
