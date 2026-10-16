import uvicorn
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from app.api.router import api_router
from app.core.exceptions import register_exception_handlers
from app.services.datalake_service import DataLakeService

# 1. Inicialização da aplicação FastAPI
app = FastAPI(
    title="AeroShield AI — Enterprise BFA Engine",
    version="1.0.0",
    description="Backend for Agents (BFA) para a equipe interna de operações e CRM da Azul: Data Lake Medalhão, MLOps e Multiagentes Preditivos."
)

# 2. Configuração de Middleware CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 3. Tratamento Global de Exceções
register_exception_handlers(app)

# 4. Inclusão do Roteador Central (/api/v1)
app.include_router(api_router)

# 5. Evento de Inicialização do Banco (DuckDB Medalhão)
@app.on_event("startup")
def startup_event():
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
