import pytest
import pandas as pd
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
CSV_PATH = BASE_DIR / "clientes_sinteticos_snowflake_2000.csv"

@pytest.fixture(scope="module")
def dataset():
    assert CSV_PATH.is_file(), f"Arquivo não encontrado: {CSV_PATH}"
    df = pd.read_csv(CSV_PATH)
    return df

def test_quantidade_exata_de_clientes(dataset):
    """Garante que a base possui exatamente 2.000 clientes."""
    assert len(dataset) == 2000, f"Esperado 2000 clientes, encontrado {len(dataset)}"

def test_unicidade_de_ids(dataset):
    """Garante que não existem clientes duplicados (ID único)."""
    assert dataset["CUSTOMER_ID"].nunique() == 2000, "Existem CUSTOMER_ID duplicados na base"

def test_ausencia_de_valores_nulos(dataset):
    """Garante que não há nenhum campo ausente ou NaN na base."""
    null_counts = dataset.isnull().sum()
    assert null_counts.sum() == 0, f"Existem campos nulos no dataset:\n{null_counts[null_counts > 0]}"

def test_conformidade_do_schema(dataset):
    """Valida se todas as colunas necessárias para o projeto estão presentes."""
    colunas_esperadas = {
        "CUSTOMER_ID", "NOME", "EMAIL", "ESTADO",
        "CATEGORIA_TIER", "PONTOS_ACUMULADOS",
        "VOOS_ANO", "RISCO_CHURN", "DATA_CADASTRO"
    }
    assert colunas_esperadas.issubset(set(dataset.columns)), "Faltam colunas obrigatórias no CSV"

def test_regras_de_negocio(dataset):
    """Valida coerência dos valores numéricos e categorias permitidas."""
    # Categorias permitidas
    tiers_validos = {"Basico", "Topazio", "Safira", "Diamante"}
    assert set(dataset["CATEGORIA_TIER"].unique()).issubset(tiers_validos)

    # Níveis de Churn permitidos
    churn_validos = {"Baixo", "Medio", "Alto"}
    assert set(dataset["RISCO_CHURN"].unique()).issubset(churn_validos)

    # Valores numéricos positivos
    assert (dataset["PONTOS_ACUMULADOS"] >= 0).all(), "Existem pontos acumulados negativos"
    assert (dataset["VOOS_ANO"] >= 0).all(), "Existem contagens de voos negativas"