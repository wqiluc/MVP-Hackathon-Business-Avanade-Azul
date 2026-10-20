import pandas as pd
import pytest
from fastapi.testclient import TestClient
from main import CSV_FILE_PATH, app
from pipeline_datalake import COLUNAS_CONTEXTO_IA

TOTAL_GOLD = len(pd.read_csv(CSV_FILE_PATH))

@pytest.fixture
def client():
    # Usa o context manager do TestClient para acionar os eventos de lifespan
    with TestClient(app) as test_client:
        yield test_client

def test_health_check(client):
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["records_loaded"] == TOTAL_GOLD

def test_metricas_contagem_total(client):
    response = client.get("/api/metrics/customer-count")
    assert response.status_code == 200
    data = response.json()
    assert data["total_clientes"] == TOTAL_GOLD
    assert len(data["por_categoria"]) > 0
    assert len(data["por_risco_churn"]) > 0
    assert len(data["por_persona"]) == 4
    assert 0 < data["total_alto_valor"] < TOTAL_GOLD

def test_paginacao_e_limites(client):
    # Teste de paginação padrão
    res = client.get("/api/customers?limit=10&offset=0")
    assert res.status_code == 200
    assert len(res.json()["data"]) == 10

    # Teste de proteção contra limite abusivo (acima de 2000 deve falhar com 422)
    res_invalido = client.get("/api/customers?limit=99999")
    assert res_invalido.status_code == 422

    # Teste de offset negativo (deve falhar com 422)
    res_offset_negativo = client.get("/api/customers?offset=-5")
    assert res_offset_negativo.status_code == 422

def test_filtro_por_tier(client):
    response = client.get("/api/customers?tier=Diamante&limit=10")
    assert response.status_code == 200
    items = response.json()["data"]
    for item in items:
        assert item["CATEGORIA_TIER"].lower() == "diamante"

def test_filtro_tier_com_caracteres_ou_vazio(client):
    # Teste com valor inexistente
    response = client.get("/api/customers?tier=CategoriaInexistente123")
    assert response.status_code == 200
    data = response.json()
    assert data["total_registros"] == 0
    assert len(data["data"]) == 0

def test_filtros_persona_e_alto_valor(client):
    response = client.get("/api/customers?persona=Executivo Frequente&alto_valor=true&limit=20")
    assert response.status_code == 200
    items = response.json()["data"]
    assert items
    assert all(i["PERSONA"] == "Executivo Frequente" and i["ALTO_VALOR"] for i in items)

def test_fila_ordenada_por_prioridade(client):
    items = client.get("/api/customers?limit=50").json()["data"]
    prioridades = [i["PRIORIDADE_CRM"] for i in items]
    assert prioridades == sorted(prioridades, reverse=True)

def test_cliente_360_e_inexistente(client):
    response = client.get("/api/customers/cli-100002")
    assert response.status_code == 200
    assert response.json()["CUSTOMER_ID"] == "CLI-100002"
    assert client.get("/api/customers/CLI-000000").status_code == 404

def test_contexto_ia_sem_dados_pessoais(client):
    data = client.get("/api/customers/CLI-100002/contexto-ia").json()
    assert set(data) == set(COLUNAS_CONTEXTO_IA)
    assert "NOME" not in data and "EMAIL" not in data