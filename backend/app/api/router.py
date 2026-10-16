from fastapi import APIRouter
from app.api.v1 import auth, clients, health, uploads

# Roteador Principal
api_router = APIRouter(prefix="/api/v1")

# Agregação das Sub-Rotas por Domínio
api_router.include_router(health.router, prefix="/health", tags=["Healthcheck"])
api_router.include_router(auth.router, prefix="/auth", tags=["Autenticação"])
api_router.include_router(uploads.router, prefix="/data", tags=["Data Lake Medalhão"])
# api_router.include_router(ml.router, prefix="/ml", tags=["MLOps / MLflow"])
api_router.include_router(clients.router, prefix="/ai", tags=["Agentes Preditivos BFA"])
