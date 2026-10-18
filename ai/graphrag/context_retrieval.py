import networkx as nx


def build_knowledge_graph() -> nx.DiGraph:
    """Build the current small, in-code policy relationship graph."""
    graph = nx.DiGraph()
    graph.add_node("Resolução 400 ANAC", type="Regulamentação")
    graph.add_node("Downgrade Involuntário", type="Incidente")
    graph.add_node("Atraso Superior a 4h", type="Incidente")
    graph.add_node("VIP World Legend", type="Tier_Fidelidade")
    graph.add_node("Voucher Trust-First", type="Acao_Retencao")
    graph.add_node("Upgrade Espaço Azul", type="Acao_Retencao")

    graph.add_edge("Downgrade Involuntário", "Resolução 400 ANAC", relation="Regulado_Por")
    graph.add_edge("Resolução 400 ANAC", "Voucher Trust-First", relation="Exige_Compensacao_Imediata")
    graph.add_edge("VIP World Legend", "Upgrade Espaço Azul", relation="Prioridade_Concessao")
    return graph


def query_context(tier: str, incident: str) -> dict:
    """Return graph paths and the existing rule-based policy context."""
    graph = build_knowledge_graph()
    graph_relations = []

    if graph.has_node(incident):
        for neighbor in graph.neighbors(incident):
            for sub_neighbor in graph.neighbors(neighbor):
                graph_relations.append(f"{incident} -> {neighbor} -> {sub_neighbor}")

    policy_context = (
        f"Regra Aplicada: Passageiro {tier} exposto ao incidente '{incident}'. "
        f"Diretriz ANAC 400 exige mitigação com tratamento Trust-First."
    )

    return {
        "tier": tier,
        "incident": incident,
        "graph_relations": graph_relations,
        "policy_context": policy_context,
    }
