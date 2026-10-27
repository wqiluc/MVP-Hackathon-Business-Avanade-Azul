from pathlib import Path
from urllib.parse import urlparse

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.router import api_router
from app.core.exceptions import register_exception_handlers
from app.config import settings
from app.services.datalake_service import DataLakeService
from app.core.ai_rate_limit import validate_ai_rate_limit_settings
from app.core.security import validate_production_auth_settings
from ml.models import mlflow_tracker

_LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1", "0.0.0.0", ""}


def _is_local_uri(uri: str) -> bool:
    value = uri.strip()
    if "://" not in value:
        return True  # caminho/arquivo local ou sqlite
    scheme = value.split("://", 1)[0].lower()
    if scheme not in {"http", "https"}:
        return True
    host = (urlparse(value).hostname or "").lower()
    return host in _LOCAL_HOSTS or host.endswith(".localhost")


def validate_production_integrations() -> None:
    """Snowflake e MLflow são obrigatórios em produção. Só valida configuração;
    não conecta a serviços externos (disponibilidade é checada em health/readiness)."""
    problems = []
    if settings.DATA_LAKE_BACKEND != "snowflake":
        problems.append("DATA_LAKE_BACKEND deve ser 'snowflake'")
    problems += [
        f"{name} é obrigatório"
        for name in (
            "SNOWFLAKE_ACCOUNT",
            "SNOWFLAKE_USER",
            "SNOWFLAKE_PASSWORD",
            "SNOWFLAKE_DATABASE",
            "SNOWFLAKE_WAREHOUSE",
        )
        if not str(getattr(settings, name) or "").strip()
    ]
    tracking = (settings.MLFLOW_TRACKING_URI or "").strip()
    if not tracking or _is_local_uri(tracking):
        problems.append("MLFLOW_TRACKING_URI deve apontar para um servidor remoto")
    if not mlflow_tracker.MODEL_NAME:
        problems.append("MLFLOW_MODEL_NAME é obrigatório")
    if settings.ML_INFERENCE_MODE == "local":
        for name, configured_path in (
            ("ML_CHURN_MODEL_PATH", settings.ML_CHURN_MODEL_PATH),
            ("ML_CLV_MODEL_PATH", settings.ML_CLV_MODEL_PATH),
        ):
            model_path = Path(configured_path).expanduser()
            if not model_path.is_absolute():
                model_path = Path(__file__).resolve().parent.parent / model_path
            if not model_path.is_dir():
                problems.append(f"{name} deve apontar para um diretório de modelo")
    elif settings.ML_INFERENCE_MODE == "databricks":
        host = urlparse(settings.DATABRICKS_HOST.strip())
        if (
            host.scheme not in {"http", "https"}
            or not host.hostname
            or host.username
            or host.password
            or host.path not in {"", "/"}
            or host.query
            or host.fragment
        ):
            problems.append("DATABRICKS_HOST deve ser uma origem http(s) válida")
        if not settings.DATABRICKS_TOKEN.strip():
            problems.append("DATABRICKS_TOKEN é obrigatório")
        for name, endpoint in (
            ("DATABRICKS_CHURN_ENDPOINT", settings.DATABRICKS_CHURN_ENDPOINT),
            ("DATABRICKS_CLV_ENDPOINT", settings.DATABRICKS_CLV_ENDPOINT),
        ):
            if not endpoint.strip():
                problems.append(f"{name} é obrigatório")
        try:
            classes = [
                int(value.strip())
                for value in settings.ML_CHURN_CLASS_ORDER.split(",")
                if value.strip()
            ]
        except ValueError:
            classes = []
        if len(classes) != 2 or len(set(classes)) != 2:
            problems.append(
                "ML_CHURN_CLASS_ORDER deve conter duas classes inteiras distintas"
            )
        elif 1 not in classes:
            problems.append("ML_CHURN_CLASS_ORDER deve incluir a classe positiva 1")
    else:
        problems.append("ML_INFERENCE_MODE deve ser 'local' ou 'databricks'")
    if problems:
        raise RuntimeError(
            "Configuração de produção inválida: " + "; ".join(problems) + "."
        )


def validate_runtime_settings() -> None:
    if settings.ENVIRONMENT.strip().lower() not in {"development", "test", "production"}:
        raise RuntimeError("ENVIRONMENT deve ser development, test ou production.")
    validate_ai_rate_limit_settings()
    if settings.MAX_UPLOAD_BYTES <= 0:
        raise RuntimeError("MAX_UPLOAD_BYTES deve ser maior que zero.")
    if settings.OPENAI_TIMEOUT_SECONDS <= 0:
        raise RuntimeError("OPENAI_TIMEOUT_SECONDS deve ser maior que zero.")
    if settings.GEMINI_TIMEOUT_SECONDS <= 0:
        raise RuntimeError("GEMINI_TIMEOUT_SECONDS deve ser maior que zero.")
    if settings.ML_INFERENCE_TIMEOUT_SECONDS <= 0:
        raise RuntimeError("ML_INFERENCE_TIMEOUT_SECONDS deve ser maior que zero.")
    if settings.ML_INFERENCE_MODE not in {"local", "databricks"}:
        raise RuntimeError("ML_INFERENCE_MODE deve ser 'local' ou 'databricks'.")
    supported_llm_providers = {"openai", "gemini", "disabled"}
    if settings.LLM_PROVIDER not in supported_llm_providers:
        raise RuntimeError("LLM_PROVIDER deve ser 'openai', 'gemini' ou 'disabled'.")
    if settings.LLM_FALLBACK_PROVIDER not in supported_llm_providers:
        raise RuntimeError(
            "LLM_FALLBACK_PROVIDER deve ser 'openai', 'gemini' ou 'disabled'."
        )
    if settings.LLM_PROVIDER == "disabled" and settings.LLM_FALLBACK_PROVIDER != "disabled":
        raise RuntimeError(
            "LLM_FALLBACK_PROVIDER deve ser 'disabled' quando LLM_PROVIDER for 'disabled'."
        )
    if (
        settings.LLM_FALLBACK_PROVIDER == settings.LLM_PROVIDER
        and settings.LLM_PROVIDER != "disabled"
    ):
        raise RuntimeError("LLM_FALLBACK_PROVIDER não pode repetir LLM_PROVIDER.")
    if settings.ACCESS_TOKEN_EXPIRE_HOURS <= 0:
        raise RuntimeError("ACCESS_TOKEN_EXPIRE_HOURS deve ser maior que zero.")

    if settings.is_production:
        validate_production_auth_settings()
        validate_production_integrations()

    origins = [origin.strip() for origin in settings.CORS_ORIGINS.split(",") if origin.strip()]
    if not origins or any(
        "*" in origin
        or urlparse(origin).scheme not in {"http", "https"}
        or not urlparse(origin).hostname
        or urlparse(origin).username
        or urlparse(origin).password
        or urlparse(origin).path not in {"", "/"}
        or urlparse(origin).query
        or urlparse(origin).fragment
        for origin in origins
    ):
        raise RuntimeError("CORS_ORIGINS deve conter origens explícitas.")
    return None

# 1. Inicialização da aplicação FastAPI
app = FastAPI(
    title="CRM de Alto Valor",
    version="1.0.0",
    description="Backend for Agents (BFA) para a equipe interna de operações e CRM da Azul: Data Lake Medalhão, MLOps e Multiagentes Preditivos."
)

register_exception_handlers(app)

# 2. Configuração de Middleware CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        origin.strip()
        for origin in settings.CORS_ORIGINS.split(",")
        if origin.strip()
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
    expose_headers=["Retry-After"],
)

# 4. Inclusão do Roteador Central (/api/v1)
app.include_router(api_router)

# 5. Evento de Inicialização do Banco (DuckDB Medalhão)
@app.on_event("startup")
def startup_event():
    validate_runtime_settings()
    if settings.DATA_LAKE_BACKEND != "snowflake":
        DataLakeService.init_schema()

# 6. Endpoint da Raiz (Healthcheck rápido)
@app.get("/", tags=["Healthcheck"])
def healthcheck():
    return {
        "status": "online",
        "service": "CRM de Alto Valor",
        "version": "1.0.0",
        "docs": "/docs"
    }

if __name__ == "__main__":
    uvicorn.run("run:app", host="0.0.0.0", port=8000, reload=True)
