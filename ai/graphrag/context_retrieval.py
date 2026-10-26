import networkx as nx


_ILLUSTRATIVE_PREMISES = {
    "categorias": (
        "Categorias Topázio, Safira e Diamante são conquistadas por pontos "
        "qualificáveis acumulados em 12 meses."
    ),
    "bonusRelacionamento": (
        "Pontos bônus de relacionamento podem ser creditados pela companhia "
        "em campanhas e ações de reconhecimento."
    ),
    "beneficiosCategoria": (
        "Clientes de categoria têm benefícios como prioridade de embarque "
        "e acesso a assentos com mais espaço."
    ),
    "pontosEmDobro": (
        "Campanhas promocionais podem multiplicar o acúmulo de pontos em "
        "rotas e períodos específicos."
    ),
}


def build_knowledge_graph() -> nx.DiGraph:
    """Represent repository premises without asserting that they are verified policy."""
    graph = nx.DiGraph()
    for premise, text in _ILLUSTRATIVE_PREMISES.items():
        graph.add_node(premise, type="premissa_ilustrativa", text=text)

    for tier in ("Básico", "Topázio", "Safira", "Diamante", "Executive", "Premium"):
        graph.add_node(tier, type="tier")
        graph.add_edge(tier, "categorias", relation="contexto_de_categoria")

    return graph


def query_context(tier: str, incident_type: str | None) -> dict:
    """Return tier context and make the unverified source status explicit."""
    graph = build_knowledge_graph()
    graph_relations = []
    if graph.has_node(tier):
        graph_relations.append(f"{tier} -> categorias")
    if incident_type:
        graph.add_node(incident_type, type="incident_input")
        graph_relations.append(
            f"{incident_type} -> revisão humana necessária"
        )

    premise_text = " ".join(_ILLUSTRATIVE_PREMISES.values())
    policy_context = (
        "Premissas ilustrativas presentes no repositório, não verificadas "
        "contra o regulamento vigente e não garantidoras de elegibilidade: "
        f"{premise_text}"
    )
    return {
        "tier": tier,
        "incident_type": incident_type,
        "graph_relations": graph_relations,
        "policy_context": policy_context,
        "policies_verified": False,
    }
