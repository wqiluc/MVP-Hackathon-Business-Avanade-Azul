import os
import secrets
from pathlib import Path
from dotenv import load_dotenv
from pydantic_settings import BaseSettings

BASE_DIR = Path(__file__).resolve().parent.parent.parent  # Diretório raiz do projeto (backend/)

load_dotenv(BASE_DIR / ".env")

class Settings(BaseSettings):
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    
    # Segurança e Autenticação
    SECRET_KEY: str = os.getenv("SECRET_KEY", secrets.token_urlsafe(32))
    JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", secrets.token_urlsafe(32))
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_HOURS: int = 8
    
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

    # Data Lake oficial: Snowflake (credenciais via .env). "duckdb" = fallback local/offline.
    DATA_LAKE_BACKEND: str = os.getenv("DATA_LAKE_BACKEND", "duckdb")
    SNOWFLAKE_USER: str = os.getenv("SNOWFLAKE_USER", "")
    SNOWFLAKE_PASSWORD: str = os.getenv("SNOWFLAKE_PASSWORD", "")
    SNOWFLAKE_ACCOUNT: str = os.getenv("SNOWFLAKE_ACCOUNT", "")
    SNOWFLAKE_WAREHOUSE: str = os.getenv("SNOWFLAKE_WAREHOUSE", "COMPUTE_WH")
    SNOWFLAKE_DATABASE: str = os.getenv("SNOWFLAKE_DATABASE", "AZUL_DATA_LAKE")
    SNOWFLAKE_ROLE: str = os.getenv("SNOWFLAKE_ROLE", "")
    SNOWFLAKE_TEST_DATABASE: str = os.getenv("SNOWFLAKE_TEST_DATABASE", "")

    # MLflow Serving (ex.: http://localhost:5000/invocations). Vazio = score por regras locais.
    MLFLOW_SERVING_URL: str = os.getenv("MLFLOW_SERVING_URL", "")

    # Acesso do front (ambiente de avaliação do Hackathon)
    DEMO_EMAIL: str = os.getenv("DEMO_EMAIL", "analista@exemplo.com")
    DEMO_PASSWORD: str = os.getenv("DEMO_PASSWORD", "azul2026")

    # class Config:
    #     env_file = ".env"
    #     env_file_encoding = "utf-8"

settings = Settings()
