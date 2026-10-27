from ai.graphrag.context_retrieval import build_knowledge_graph, query_context
from ai.rag.embeddings import VECTOR_DB_DIR


def get_free_embeddings():
    from ai.rag.embeddings import get_free_embeddings as create_embeddings

    return create_embeddings()