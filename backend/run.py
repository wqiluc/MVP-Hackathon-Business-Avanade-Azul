from urllib.parse import urlparse

import uvicorn
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from app.api.router import api_router
from app.core.exceptions import register_exception_handlers
from app.config import settings
from app.services.datalake_service import DataLakeService
from app.core.ai_rate_limit import validate_ai_rate_limit_settings

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
    serving = (settings.MLFLOW_SERVING_URL or "").strip()
    if not serving:
        problems.append("MLFLOW_SERVING_URL é obrigatório")
    elif urlparse(serving).scheme not in {"http", "https"}:
        problems.append("MLFLOW_SERVING_URL deve ser uma URL http(s)")
    if settings.MLFLOW_LOCAL_INFERENCE:
        problems.append("MLFLOW_LOCAL_INFERENCE deve ser false")
    if problems:
        raise RuntimeError(
            "Configuração de produção inválida: " + "; ".join(problems) + "."
        )


def validate_runtime_settings() -> None:
    validate_ai_rate_limit_settings()
    if settings.MAX_UPLOAD_BYTES <= 0:
        raise RuntimeError("MAX_UPLOAD_BYTES deve ser maior que zero.")
    if settings.OPENAI_TIMEOUT_SECONDS <= 0:
        raise RuntimeError("OPENAI_TIMEOUT_SECONDS deve ser maior que zero.")
    if settings.LLM_PROVIDER not in {"openai", "disabled"}:
        raise RuntimeError("LLM_PROVIDER deve ser 'openai' ou 'disabled'.")

    if settings.ENVIRONMENT.lower() == "production":
        if (
            not settings.JWT_SECRET_CONFIGURED
            or settings.JWT_SECRET_KEY == "replace-with-a-random-secret"
        ):
            raise RuntimeError("Defina JWT_SECRET_KEY antes de iniciar em produção.")
        if not settings.ADMIN_EMAIL or not settings.ADMIN_PASSWORD:
            raise RuntimeError("Defina ADMIN_EMAIL e ADMIN_PASSWORD em produção.")
        validate_production_integrations()

    origins = [origin.strip() for origin in settings.CORS_ORIGINS.split(",") if origin.strip()]
    if not origins or "*" in origins:
        raise RuntimeError("CORS_ORIGINS deve conter origens explícitas.")
    return None

# 1. Inicialização da aplicação FastAPI
app = FastAPI(
    title="AeroShield AI — Enterprise BFA Engine",
    version="1.0.0",
    description="Backend for Agents (BFA) para a equipe interna de operações e CRM da Azul: Data Lake Medalhão, MLOps e Multiagentes Preditivos."
)

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

# 3. Tratamento Global de Exceções
register_exception_handlers(app)

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
        "service": "AeroShield AI BFA",
        "version": "1.0.0",
        "docs": "/docs"
    }

if __name__ == "__main__":
    uvicorn.run("run:app", host="0.0.0.0", port=8000, reload=True)
