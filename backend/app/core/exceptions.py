import logging

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)


def _safe_server_detail(request: Request, exc: StarletteHTTPException):
    detail = exc.detail
    if exc.status_code == 503 and isinstance(detail, dict):
        if detail.get("code") == "AI_RATE_LIMIT_UNAVAILABLE":
            return {
                "code": "AI_RATE_LIMIT_UNAVAILABLE",
                "message": "Proteção de IA temporariamente indisponível. Tente novamente.",
            }
        if request.url.path == "/api/v1/health/ready":
            checks = {
                key: detail[key]
                for key in (
                    "data_lake_backend", "mlflow_tracking_configured",
                    "upload_limit_configured", "snowflake_credentials_configured",
                )
                if isinstance(detail.get(key), bool)
            }
            dependencies = detail.get("dependencies", {})
            return {
                "message": "Dependências ou configurações obrigatórias indisponíveis.",
                **checks,
                "dependencies": {
                    key: value
                    for key, value in dependencies.items()
                    if key in {"data_lake", "mlflow_tracking", "mlflow_serving", "redis"}
                    and isinstance(value, str)
                    and value in {"ready", "failed", "unverified", "not_configured"}
                } if isinstance(dependencies, dict) else {},
            }
    return "Erro interno do servidor."


def register_exception_handlers(app: FastAPI) -> None:
    """
    Registra os manipuladores globais de exceção na aplicação FastAPI.
    Garante um formato padronizado de resposta de erro JSON para o frontend.
    """

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        detail = exc.detail
        if exc.status_code >= 500:
            detail = _safe_server_detail(request, exc)
        message = detail.get("message", "A requisição não pôde ser processada.") if isinstance(detail, dict) else detail
        content = {
            "success": False,
            "error": detail.get("code", "HTTP_ERROR") if isinstance(detail, dict) else "HTTP_ERROR",
            "message": message,
            "detail": detail,
            "status_code": exc.status_code,
            "path": request.url.path,
        }
        if isinstance(detail, dict):
            content.update(
                {
                    key: detail[key]
                    for key in ("missing_columns", "invalid_columns", "ingestion_contract")
                    if key in detail
                }
            )
        return JSONResponse(status_code=exc.status_code, content=content, headers=exc.headers)

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "success": False,
                "error": "VALIDATION_ERROR",
                "message": "Erro de validação nos dados enviados na requisição.",
                "details": [
                    {
                        "loc": error.get("loc"),
                        "msg": error.get("msg"),
                        "type": error.get("type"),
                    }
                    for error in exc.errors()
                ],
                "path": request.url.path,
            },
        )

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        logger.error("Unhandled API error; type=%s", type(exc).__name__)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "success": False,
                "error": "INTERNAL_SERVER_ERROR",
                "message": "Erro interno do servidor.",
                "path": request.url.path,
            },
        )

    @app.middleware("http")
    async def contain_internal_errors(request: Request, call_next):
        try:
            return await call_next(request)
        except Exception as error:
            # Contain the exception before the server logs its raw message/traceback.
            return await global_exception_handler(request, error)
