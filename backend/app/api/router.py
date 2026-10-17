from fastapi import APIRouter
from app.api.v1 import auth, clients, dashboard, health, ml, uploads

api_router = APIRouter(prefix="/api/v1")

# Rotas diretas exigidas pelo contrato do Front
api_router.include_router(auth.router, prefix="/auth", tags=["Autenticação"])
api_router.include_router(uploads.router, prefix="/ingestao", tags=["Ingestão Medalhão"])
api_router.include_router(dashboard.router, prefix="/dashboard", tags=["Dashboard CRM"])
api_router.include_router(clients.router, prefix="/clientes", tags=["Gestão de Clientes & IA"])
api_router.include_router(ml.router, prefix="/modelo", tags=["MLOps / MLflow Metrics"])
api_router.include_router(health.router, prefix="/health", tags=["Healthcheck"])

# Aliases legados (não quebram consumidores anteriores)
api_router.include_router(uploads.router, prefix="/data", tags=["Legado"], include_in_schema=False)
api_router.include_router(clients.router, prefix="/ai", tags=["Legado"], include_in_schema=False)
api_router.include_router(ml.router, prefix="/ml", tags=["Legado"], include_in_schema=False)
