import os


VECTOR_DB_DIR = "data/vectordb"


def get_free_embeddings():
    """Construct the existing local CPU embedding helper when explicitly requested."""
    from langchain_community.embeddings import HuggingFaceEmbeddings

    cache_folder = os.path.join("data", "models_cache")
    os.makedirs(cache_folder, exist_ok=True)
    return HuggingFaceEmbeddings(
        model_name="sentence-transformers/all-MiniLM-L6-v2",
        cache_folder=cache_folder,
        model_kwargs={"device": "cpu"},
        encode_kwargs={"normalize_embeddings": True},
    )
