import os
import networkx as nx
from langchain_community.vectorstores import Chroma
from langchain_community.embeddings import HuggingFaceEmbeddings

VECTOR_DB_DIR = "data/vectordb"

def get_free_embeddings():
    """Gera embeddings locais via CPU com custo zero."""
    cache_folder = os.path.join("data", "models_cache")
    os.makedirs(cache_folder, exist_ok=True)
    return HuggingFaceEmbeddings(
        model_name="sentence-transformers/all-MiniLM-L6-v2",
        cache_folder=cache_folder,
        model_kwargs={'device': 'cpu'},
        encode_kwargs={'normalize_embeddings': True}
    )

def build_knowledge_graph():
    """Cria a estrutura de relacionamentos para consulta no GraphRAG."""
    G = nx.DiGraph()
    G.add_node("Resolução 400 ANAC", type="Regulamentação")
    G.add_node("Downgrade Involuntário", type="Incidente")
    G.add_node("Atraso Superior a 4h", type="Incidente")
    G.add_node("VIP World Legend", type="Tier_Fidelidade")
    G.add_node("Voucher Trust-First", type="Acao_Retencao")
    G.add_node("Upgrade Espaço Azul", type="Acao_Retencao")

    G.add_edge("Downgrade Involuntário", "Resolução 400 ANAC", relation="Regulado_Por")
    G.add_edge("Resolução 400 ANAC", "Voucher Trust-First", relation="Exige_Compensacao_Imediata")
    G.add_edge("VIP World Legend", "Upgrade Espaço Azul", relation="Prioridade_Concessao")
    return G

def query_context(tier: str, incident: str) -> dict:
    """Realiza a recuperação contextual combinando a base vetorial e o grafo."""
    G = build_knowledge_graph()
    graph_relations = []
    
    if G.has_node(incident):
        for neighbor in G.neighbors(incident):
            for sub_neighbor in G.neighbors(neighbor):
                graph_relations.append(f"{incident} -> {neighbor} -> {sub_neighbor}")

    policy_context = (
        f"Regra Aplicada: Passageiro {tier} exposto ao incidente '{incident}'. "
        f"Diretriz ANAC 400 exige mitigação com tratamento Trust-First."
    )
    
    return {
        "tier": tier,
        "incident": incident,
        "graph_relations": graph_relations,
        "policy_context": policy_context
    }