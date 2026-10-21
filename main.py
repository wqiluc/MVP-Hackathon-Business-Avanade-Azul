import json
import os
from pathlib import Path
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd

from pipeline_datalake import COLUNAS_CONTEXTO_IA, GOLD_CSV

# Camada Gold (gerada localmente ou trazida do Snowflake por `python pipeline_datalake.py trazer`)
CSV_FILE_PATH = GOLD_CSV

# Cache global em memória
DATA_STORE = {"df": None}


def normalizar_colunas(df: pd.DataFrame) -> pd.DataFrame:
    """Padroniza cabeçalhos em maiúsculo e garante compatibilidade entre CLIENTE_ID e CUSTOMER_ID."""
    df.columns = [col.upper().strip() for col in df.columns]
    
    # Compatibilidade entre nomes de chave primária
    if "CLIENTE_ID" in df.columns and "CUSTOMER_ID" not in df.columns:
        df["CUSTOMER_ID"] = df["CLIENTE_ID"]
    elif "CUSTOMER_ID" in df.columns and "CLIENTE_ID" not in df.columns:
        df["CLIENTE_ID"] = df["CUSTOMER_ID"]
        
    return df


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Carrega os dados de forma segura na inicialização da aplicação."""
    if not CSV_FILE_PATH.is_file():
        raise RuntimeError(
            f"Arquivo de dados crítico não encontrado: {CSV_FILE_PATH}. "
            "Execute 'python pipeline_datalake.py trazer' para baixar a Gold do Snowflake."
        )

    # Carrega uma única vez no startup para blindar I/O
    df_carregado = pd.read_csv(CSV_FILE_PATH)
    DATA_STORE["df"] = normalizar_colunas(df_carregado)
    yield
    # Limpeza no shutdown
    DATA_STORE.clear()


app = FastAPI(
    title="Azul Retenção & Fidelidade Analytics API",
    description="API para consumo das camadas tratadas (Silver/Gold) do Snowflake",
    version="1.1.0",
    lifespan=lifespan,
)

# CORS restrito (configurável via env)
ALLOWED_ORIGINS = os.getenv(
    "ALLOWED_ORIGINS", "http://localhost:3000,http://localhost:5173"
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET"],
    allow_headers=["*"],
)


def get_dataframe() -> pd.DataFrame:
    df = DATA_STORE.get("df")
    if df is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Base de dados temporariamente indisponível no servidor.",
        )
    return df


def to_records(df: pd.DataFrame) -> list[dict]:
    """Serializa para JSON convertendo NaN e NaT em null."""
    return json.loads(df.to_json(orient="records", force_ascii=False, date_format="iso"))


def contar(df: pd.DataFrame, coluna: str, chave: str) -> list[dict]:
    if coluna not in df.columns:
        return []
    return (
        df[coluna]
        .dropna()
        .value_counts()
        .reset_index()
        .rename(columns={coluna: chave, "count": "total"})
        .to_dict(orient="records")
    )


@app.get("/health", tags=["Monitoramento"])
def health_check():
    """Endpoint leve para verificação de integridade."""
    df = get_dataframe()
    return {
        "status": "healthy",
        "records_loaded": len(df),
        "source": str(CSV_FILE_PATH.name),
    }


@app.get("/api/metrics/customer-count", tags=["Métricas"])
def get_customer_metrics():
    df = get_dataframe()
    total = len(df)

    # Suporte tanto a CATEGORIA_TIER quanto TIER vindos do Snowflake
    tier_col = "CATEGORIA_TIER" if "CATEGORIA_TIER" in df.columns else "TIER"
    churn_col = "RISCO_CHURN" if "RISCO_CHURN" in df.columns else "CHURN_180D"

    tier_counts = contar(df, tier_col, "tier")
    churn_counts = contar(df, churn_col, "risco")

    total_alto_valor = (
        int(df["ALTO_VALOR"].sum())
        if "ALTO_VALOR" in df.columns
        else int((df.get("CLV_12M", pd.Series([0])) > 15000).sum())
    )

    return {
        "total_clientes": total,
        "por_categoria": tier_counts,
        "por_risco_churn": churn_counts,
        "por_persona": contar(df, "PERSONA", "persona"),
        "por_acao_recomendada": contar(df, "ACAO_RECOMENDADA", "acao"),
        "total_alto_valor": total_alto_valor,
    }


@app.get("/api/customers", tags=["Clientes"])
def get_customers(
    limit: int = Query(50, ge=1, le=10000, description="Quantidade de registros por requisição"),
    offset: int = Query(0, ge=0, description="Deslocamento inicial"),
    tier: Optional[str] = Query(None, max_length=50, description="Filtro de categoria sanitizado"),
    persona: Optional[str] = Query(None, max_length=50, description="Filtro de persona"),
    alto_valor: Optional[bool] = Query(None, description="Somente clientes de alto valor"),
):
    """Fila do CRM com paginação ajustada para até 10.000 clientes."""
    df = get_dataframe()
    tier_col = "CATEGORIA_TIER" if "CATEGORIA_TIER" in df.columns else "TIER"

    if tier and tier_col in df.columns:
        df = df[df[tier_col].astype(str).str.lower() == tier.strip().lower()]

    if persona and "PERSONA" in df.columns:
        df = df[df["PERSONA"].astype(str).str.lower() == persona.strip().lower()]

    if alto_valor is not None and "ALTO_VALOR" in df.columns:
        df = df[df["ALTO_VALOR"] == alto_valor]

    total_filtrado = len(df)
    paginated_df = df.iloc[offset : offset + limit]

    return {
        "total_registros": total_filtrado,
        "limit": limit,
        "offset": offset,
        "data": to_records(paginated_df),
    }


def get_customer_row(customer_id: str) -> pd.DataFrame:
    df = get_dataframe()
    cid_sanitizado = customer_id.strip().upper()
    linha = df[df["CUSTOMER_ID"].astype(str).str.upper() == cid_sanitizado]

    if linha.empty:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Cliente com identificador '{customer_id}' não encontrado.",
        )
    return linha


@app.get("/api/customers/{customer_id}", tags=["Clientes"])
def get_customer(customer_id: str):
    """Visão 360 completa do cliente para a tela do operador de CRM."""
    return to_records(get_customer_row(customer_id))[0]


@app.get("/api/customers/{customer_id}/contexto-ia", tags=["IA"])
def get_customer_ai_context(customer_id: str):
    """Payload enviado ao agente de IA: restrito a COLUNAS_CONTEXTO_IA, blindando CPF e dados sensíveis (LGPD)."""
    row = get_customer_row(customer_id)
    colunas_disponiveis = [col for col in COLUNAS_CONTEXTO_IA if col in row.columns]
    
    if not colunas_disponiveis:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Nenhuma coluna válida de contexto para IA foi encontrada na base.",
        )

    return to_records(row[colunas_disponiveis])[0]