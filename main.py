import os
from pathlib import Path
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd

# Caminho seguro e absoluto para o arquivo de dados
BASE_DIR = Path(__file__).resolve().parent
CSV_FILE_PATH = BASE_DIR / "clientes_sinteticos_snowflake_2000.csv"

# Cache global em memória
DATA_STORE = {"df": None}

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Carrega os dados de forma segura na inicialização da aplicação."""
    if not CSV_FILE_PATH.is_file():
        raise RuntimeError(f"Arquivo de dados crítico não encontrado: {CSV_FILE_PATH}")
    
    # Carrega uma única vez no startup para blindar I/O
    DATA_STORE["df"] = pd.read_csv(CSV_FILE_PATH)
    yield
    # Limpeza no shutdown
    DATA_STORE.clear()

app = FastAPI(
    title="Azul Local Analytics API",
    version="1.0.0",
    lifespan=lifespan
)

# CORS restrito (configurável via env)
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000,http://localhost:5173").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET"],  # Apenas leitura necessária para este microsserviço
    allow_headers=["*"],
)

def get_dataframe() -> pd.DataFrame:
    df = DATA_STORE.get("df")
    if df is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Base de dados temporariamente indisponível."
        )
    return df

@app.get("/health", tags=["Monitoramento"])
def health_check():
    """Endpoint leve para verificação de integridade (Health Check)."""
    return {"status": "healthy", "records_loaded": len(get_dataframe())}

@app.get("/api/metrics/customer-count", tags=["Métricas"])
def get_customer_metrics():
    df = get_dataframe()
    total = len(df)

    tier_counts = (
        df["CATEGORIA_TIER"]
        .value_counts()
        .reset_index()
        .rename(columns={"CATEGORIA_TIER": "tier", "count": "total"})
        .to_dict(orient="records")
    )

    churn_counts = (
        df["RISCO_CHURN"]
        .value_counts()
        .reset_index()
        .rename(columns={"RISCO_CHURN": "risco", "count": "total"})
        .to_dict(orient="records")
    )

    return {
        "total_clientes": total,
        "por_categoria": tier_counts,
        "por_risco_churn": churn_counts
    }

@app.get("/api/customers", tags=["Clientes"])
def get_customers(
    limit: int = Query(50, ge=1, le=2000, description="Quantidade de registros por requisição"),
    offset: int = Query(0, ge=0, description="Deslocamento inicial"),
    tier: Optional[str] = Query(None, max_length=50, description="Filtro de categoria sanitizado")
):
    df = get_dataframe()

    if tier:
        sanitized_tier = tier.strip().lower()
        df = df[df["CATEGORIA_TIER"].astype(str).str.lower() == sanitized_tier]

    total_filtrado = len(df)
    paginated_df = df.iloc[offset : offset + limit]

    return {
        "total_registros": total_filtrado,
        "limit": limit,
        "offset": offset,
        "data": paginated_df.to_dict(orient="records")
    }