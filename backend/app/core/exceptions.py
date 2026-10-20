import logging

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)

def register_exception_handlers(app: FastAPI) -> None:
    """
    Registra os manipuladores globais de exceção na aplicação FastAPI.
    Garante um formato padronizado de resposta de erro JSON para o frontend.
    """

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        detail = exc.detail
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
                    for key in ("missing_columns", "invalid_columns")
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
        logger.exception("Unhandled API error for %s", request.url.path)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "success": False,
                "error": "INTERNAL_SERVER_ERROR",
                "message": "Erro interno do servidor.",
                "path": request.url.path,
            },
        )
