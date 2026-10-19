from typing import TypedDict

from langgraph.graph import END, StateGraph

from ai.graphrag.context_retrieval import query_context


class AgentState(TypedDict):
    client_identifier: str
    frequency: int
    total_spend: float
    churn_score: float | None
    flight_incidents: int
    incident_type: str | None
    tier: str
    value_at_risk: float
    graph_rag_context: dict
    decision: dict
    audit_status: str


def query_manager_agent(state: AgentState) -> AgentState:
    """Calculate monetary exposure from the supplied model score."""
    spend = state["total_spend"]
    churn_score = state["churn_score"]
    state["value_at_risk"] = (
        round(spend * 1.30 * churn_score, 2) if churn_score is not None else 0.0
    )

    if not state["tier"]:
        if spend >= 80000:
            state["tier"] = "VIP World Legend"
        elif spend >= 35000:
            state["tier"] = "Executive"
        else:
            state["tier"] = "Premium"
    return state


def graph_rag_agent(state: AgentState) -> AgentState:
    """Retrieve context from the current NetworkX policy graph."""
    state["graph_rag_context"] = query_context(
        state["tier"], state["incident_type"]
    )
    return state


def decision_agent(state: AgentState) -> AgentState:
    """Choose a retention action from the model score, business rules and graph evidence."""
    graph_context = state["graph_rag_context"]
    graph_relations = graph_context.get("graph_relations", [])
    policies_verified = graph_context.get("policies_verified") is True
    churn_score = state["churn_score"]
    value_at_risk = state["value_at_risk"]
    tier = state["tier"]
    high_model_score = churn_score is not None and churn_score >= 0.5
    high_business_risk = (
        high_model_score
        or value_at_risk > 5000
        or tier in {"VIP World Legend", "Diamante"}
    )
    incident_needs_review = state["flight_incidents"] >= 2 or (
        state["flight_incidents"] > 0 and bool(state["incident_type"])
    )

    evidence = [
        f"Tier CRM: {tier}",
        f"Incidentes de voo: {state['flight_incidents']}",
        f"Valor em risco calculado: R$ {value_at_risk:.2f}",
        (
            "Contexto de política marcado como verificado; elegibilidade individual "
            "não confirmada."
            if policies_verified
            else "Contexto de política não verificado; proposta apenas demonstrativa."
        ),
        *graph_relations,
    ]
    if state["incident_type"]:
        evidence.append(f"Tipo de incidente informado: {state['incident_type']}")
    policy_context = graph_context.get("policy_context")
    if policy_context:
        evidence.append(policy_context)
    if churn_score is not None:
        evidence.append(
            f"Score do classificador para high_risk_flag: {churn_score:.3f}; "
            "não representa churn observado."
        )

    if incident_needs_review:
        reasoning = (
            "Há incidentes registrados; encaminhar para análise humana antes "
            "de avaliar qualquer compensação ou benefício. "
            + (
                "O contexto de política está marcado como verificado, mas a "
                "elegibilidade individual ainda precisa ser confirmada."
                if policies_verified
                else "A política não foi verificada; não apresentar a proposta "
                "demonstrativa como oferta vigente."
            )
        )
        proposal = {
            "strategy": (
                "Revisão de atendimento — política verificada; validar elegibilidade"
                if policies_verified
                else "Revisão de atendimento — simulação; política não verificada"
            ),
            "voucher_value": 0.0,
            "benefit": (
                "Um analista deve validar o caso e a elegibilidade individual antes "
                "de comunicar qualquer opção."
                if policies_verified
                else "Demonstração não verificada: um analista deve consultar a política "
                "vigente antes de comunicar qualquer opção."
            ),
            "bonus_points": 0,
        }
        action_code = "recuperacao-servico"
    elif high_business_risk:
        reasoning = (
            "O classificador sinaliza high_risk_flag ou o segmento requer "
            "priorização; o score não é uma observação de churn. "
            + (
                "Usar somente o contexto de política marcado como verificado e "
                "confirmar elegibilidade individual."
                if policies_verified
                else "Qualquer benefício é apenas demonstrativo até a verificação "
                "da política vigente."
            )
        )
        proposal = {
            "strategy": (
                "Contato de relacionamento — política verificada; validar elegibilidade"
                if policies_verified
                else "Contato de relacionamento — simulação; política não verificada"
            ),
            "voucher_value": 0.0,
            "benefit": (
                "Entender a necessidade e confirmar a elegibilidade individual antes "
                "de apresentar opções."
                if policies_verified
                else "Demonstração não verificada: entender a necessidade e consultar "
                "a política vigente antes de apresentar opções."
            ),
            "bonus_points": 0,
        }
        action_code = "comunicacao"
    else:
        reasoning = (
            "Não há score do modelo disponível; sugerir contato informativo "
            "sem presumir risco ou elegibilidade."
            if churn_score is None
            else "Sugerir contato informativo com base nos dados de relacionamento."
        )
        reasoning += (
            " O contexto de política está marcado como verificado, mas a elegibilidade "
            "individual deve ser confirmada."
            if policies_verified
            else " A política não foi verificada; a sugestão é demonstrativa."
        )
        proposal = {
            "strategy": (
                "Contato informativo — política verificada; validar elegibilidade"
                if policies_verified
                else "Contato informativo — simulação; política não verificada"
            ),
            "voucher_value": 0.0,
            "benefit": (
                "Apresentar informações e confirmar a elegibilidade individual antes "
                "de comunicar opções."
                if policies_verified
                else "Demonstração não verificada: apresentar informações e validar a "
                "política vigente antes de comunicar opções."
            ),
            "bonus_points": 0,
        }
        action_code = "comunicacao"

    state["decision"] = {
        "action_code": action_code,
        "strategy": proposal["strategy"],
        "reasoning": reasoning,
        "evidence": evidence,
        "proposal": {
            "voucher_value": proposal["voucher_value"],
            "benefit": proposal["benefit"],
            "bonus_points": proposal["bonus_points"],
        },
    }
    return state


def audit_agent(state: AgentState) -> AgentState:
    """Mark that the deterministic workflow completed; this is not a compliance audit."""
    state["audit_status"] = "WORKFLOW_COMPLETE"
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


_agent_workflow = build_multi_agent_system()


def invoke_agent_workflow(state: AgentState) -> AgentState:
    return _agent_workflow.invoke(state)
