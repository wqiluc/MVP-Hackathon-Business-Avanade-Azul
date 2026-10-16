import os
import secrets
from pathlib import Path
from pydantic_settings import BaseSettings

BASE_DIR = Path(__file__).resolve().parent.parent.parent  # Diretório raiz do projeto (backend/)

class Settings(BaseSettings):
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    
    # Segurança e Autenticação
    SECRET_KEY: str = os.getenv("SECRET_KEY", secrets.token_urlsafe(32))
    JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", secrets.token_urlsafe(32))
    ALGORITHM: str = "HS256"
    ACESS_TOKEN_EXPIRE_HOURS: int = 8
    
    # Provedores de IA (Modo Free vs Produção)  
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "ollama")  # 'ollama' ou 'openai'
    OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "llama3")
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    
    # Observabilidade (LangSmith Rate-Limited)
    LANGCHAIN_TRACING_V2: str = os.getenv("LANGCHAIN_TRACING_V2", "false")
    LANGCHAIN_API_KEY: str = os.getenv("LANGCHAIN_API_KEY", "")
    LANGCHAIN_PROJECT: str = os.getenv("LANGCHAIN_PROJECT", "azul-crm-aeroshield")
    
    # Data Lake e Embeddings
    DUCKDB_PATH: str = str(BASE_DIR / "data" / "processed" / "azul_datalake.duckdb")
    VECTORDB_PATH: str = str(BASE_DIR / "data" / "vectordb")

    # class Config:
    #     env_file = ".env"
    #     env_file_encoding = "utf-8"

settings = Settings()
