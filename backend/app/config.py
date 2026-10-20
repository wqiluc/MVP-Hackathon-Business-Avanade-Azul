import os
import secrets
from pathlib import Path
from dotenv import load_dotenv
from pydantic_settings import BaseSettings

BASE_DIR = Path(__file__).resolve().parent.parent.parent

load_dotenv(BASE_DIR / "backend" / ".env")
load_dotenv(BASE_DIR / ".env")

class Settings(BaseSettings):
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    
    # Segurança e Autenticação
    JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", secrets.token_urlsafe(32))
    JWT_SECRET_CONFIGURED: bool = bool(os.getenv("JWT_SECRET_KEY"))
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_HOURS: int = 8
    CORS_ORIGINS: str = os.getenv(
        "CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
    )
    MAX_UPLOAD_BYTES: int = int(os.getenv("MAX_UPLOAD_BYTES", str(10 * 1024 * 1024)))
    
    # Provedores de IA (Modo Free vs Produção)  
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "openai").strip().lower()
    OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "llama3")
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    OPENAI_TIMEOUT_SECONDS: float = float(os.getenv("OPENAI_TIMEOUT_SECONDS", "12"))
    AI_RATE_LIMIT_ENABLED: bool = True
    AI_RATE_LIMIT_REQUESTS: int = 10
    AI_RATE_LIMIT_WINDOW_SECONDS: int = 60
    AI_RATE_LIMIT_IP_REQUESTS: int = 100
    AI_OPENAI_MAX_RETRIES: int = 2
    REDIS_URL: str = ""
    
    # Observabilidade (LangSmith Rate-Limited)
    LANGCHAIN_TRACING_V2: str = os.getenv("LANGCHAIN_TRACING_V2", "false")
    LANGCHAIN_API_KEY: str = os.getenv("LANGCHAIN_API_KEY", "")
    LANGCHAIN_PROJECT: str = os.getenv("LANGCHAIN_PROJECT", "crm-alto-valor-azul")
    
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

    # MLflow Tracking and Serving are separate processes.
    MLFLOW_TRACKING_URI: str = os.getenv(
        "MLFLOW_TRACKING_URI",
        "http://localhost:5000",
    )
    MLFLOW_SERVING_URL: str = os.getenv("MLFLOW_SERVING_URL", "")
    MLFLOW_LOCAL_INFERENCE: bool = (
        os.getenv("MLFLOW_LOCAL_INFERENCE", "false").lower() == "true"
    )

    # Acesso do front (ambiente de avaliação do Hackathon)
    DEMO_EMAIL: str = os.getenv("DEMO_EMAIL", "")
    DEMO_PASSWORD: str = os.getenv("DEMO_PASSWORD", "")
    ADMIN_EMAIL: str = os.getenv("ADMIN_EMAIL", "")
    ADMIN_PASSWORD: str = os.getenv("ADMIN_PASSWORD", "")

    # class Config:
    #     env_file = ".env"
    #     env_file_encoding = "utf-8"

settings = Settings()
