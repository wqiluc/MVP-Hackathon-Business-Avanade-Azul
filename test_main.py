import pytest
from fastapi.testclient import TestClient
from main import app

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
    assert data["records_loaded"] == 2000

def test_metricas_contagem_total(client):
    response = client.get("/api/metrics/customer-count")
    assert response.status_code == 200
    data = response.json()
    assert data["total_clientes"] == 2000
    assert len(data["por_categoria"]) > 0
    assert len(data["por_risco_churn"]) > 0

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