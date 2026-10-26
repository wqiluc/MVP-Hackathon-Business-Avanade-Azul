from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from app.services.schemas.client_schema import ClientAnalysisRequest, ClientAnalysisResponse
from app.services.crm_service import CrmService, gerar_recomendacao
from app.core.security import get_current_user
from app.core.ai_rate_limit import enforce_ai_rate_limit
from app.services.agent_service import analyze_client as analyze_client_service

router = APIRouter()

@router.post(
    "/analyze-client", include_in_schema=False,
    dependencies=[Depends(enforce_ai_rate_limit)],
)
@router.post(
    "/analyze", response_model=ClientAnalysisResponse,
    dependencies=[Depends(enforce_ai_rate_limit)],
)
def analyze_client(req: ClientAnalysisRequest, current_user: dict = Depends(get_current_user)):
    final_state = analyze_client_service(
        req.raw_user_id,
        req.frequency,
        req.total_spend,
        req.incidents,
        req.incident_type,
    )
    
    return ClientAnalysisResponse(
        audience="Equipe Interna da Azul",
        client_identifier=final_state["client_identifier"],
        metrics={
            "tier": final_state["tier"],
            "churn_score": final_state["churn_score"],
            # Legacy response alias; no independent churn_risk is calculated.
            "churn_risk": final_state["churn_score"],
            "value_at_risk": final_state["value_at_risk"],
        },
        graph_rag_context=final_state["graph_rag_context"],
        reasoning=final_state["decision"]["reasoning"],
        action_proposal={
            "strategy": final_state["decision"]["strategy"],
            **final_state["decision"]["proposal"],
        },
        audit_status=final_state["audit_status"],
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
    internal_fields = {"_churn_score", "_flight_incidents", "_incident_type"}
    return {key: value for key, value in cliente.items() if key not in internal_fields}


@router.post(
    "/{cliente_id}/recomendacao",
    dependencies=[Depends(enforce_ai_rate_limit)],
    responses={429: {"description": "Limite de IA excedido; consulte Retry-After."},
               503: {"description": "Proteção de IA indisponível."}},
)
def recomendar(cliente_id: str, current_user: dict = Depends(get_current_user)):
    cliente = CrmService.obter(cliente_id)
    if not cliente:
        raise HTTPException(status_code=404, detail="Cliente não encontrado.")
    return gerar_recomendacao(cliente)
