import ast
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from app.services.crm_service import gerar_recomendacao
from run import app

client = TestClient(app)


def test_crm_service_does_not_import_clients_api():
    service_path = Path(__file__).parents[1] / "app" / "services" / "crm_service.py"
    tree = ast.parse(service_path.read_text(encoding="utf-8"))

    imported_modules = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.append(node.module)

    assert not any(
        module == "app.api.v1.clients" or module.startswith("app.api.v1.clients.")
        for module in imported_modules
    )


def test_swagger_docs():
    res = client.get("/docs")
    assert res.status_code == 200

def test_login_flow():
    res = client.post("/api/v1/auth/login", json={"username": "analista_azul", "password": "azul123"})
    assert res.status_code == 200
    assert "access_token" in res.json()

def test_unauthorized_access():
    res = client.post("/api/v1/ai/analyze-client", json={
        "raw_user_id": "12345678900",
        "frequency": 10,
        "total_spend": 50000.0,
        "incidents": 2
    })
    assert res.status_code == 401

def test_full_analysis_pipeline():
    # 1. Login
    login_res = client.post("/api/v1/auth/login", json={"username": "analista_azul", "password": "azul123"})
    token = login_res.json()["access_token"]
    
    # 2. Análise com Token
    headers = {"Authorization": f"Bearer {token}"}
    payload = {
        "raw_user_id": "99988877700",
        "frequency": 15,
        "total_spend": 85000.0,
        "incidents": 2,
        "incident_type": "Downgrade Involuntário"
    }
    
    res = client.post("/api/v1/ai/analyze-client", headers=headers, json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["client_identifier"].startswith("AZ-")
    assert data["metrics"]["tier"] == "VIP World Legend"
    assert data["audit_status"] == "PASSED_TRUST_FIRST_AUDIT"


def test_current_client_analysis_endpoint():
    login = client.post("/api/v1/auth/login", json={"username": "analista_azul", "password": "azul123"})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    response = client.post(
        "/api/v1/clientes/analyze",
        headers=headers,
        json={
            "raw_user_id": "99988877700",
            "frequency": 15,
            "total_spend": 85000.0,
            "incidents": 2,
            "incident_type": "Downgrade Involuntário",
        },
    )

    assert response.status_code == 200
    assert response.json()["metrics"]["tier"] == "VIP World Legend"
    assert response.json()["audit_status"] == "PASSED_TRUST_FIRST_AUDIT"


def test_recommendation_falls_back_when_agent_workflow_fails():
    base_action = {"tipo": "simulacao", "titulo": "Ação por regras"}
    cliente = {
        "proximaAcao": base_action,
        "id": "AZ-test",
        "voos12m": 10,
        "receita12m": 50000.0,
        "sentimentoScore": 0.5,
    }

    with patch("app.services.crm_service.invoke_agent_workflow", side_effect=RuntimeError("workflow error")):
        assert gerar_recomendacao(cliente) == base_action


def test_front_contract_flow(tmp_path):
    res = client.post("/api/v1/auth/login", json={"email": "analista@exemplo.com", "senha": "azul2026"})
    assert res.status_code == 200
    body = res.json()
    assert body["token"] and body["usuario"]["perfil"] == "analista" and body["expiraEm"]
    headers = {"Authorization": f"Bearer {body['token']}"}

    csv = tmp_path / "base.csv"
    csv.write_text(
        "id_cliente,tier,frequencia,recencia_dias,gasto_total,incidentes\n"
        + "\n".join(f"{i},DIAMANTE,{10 + i},{i * 10},{5000 * i},{i % 3}" for i in range(1, 9))
    )
    with open(csv, "rb") as f:
        up = client.post("/api/v1/ingestao/clientes", headers=headers, files={"arquivo": ("base.csv", f)})
    assert up.status_code == 200 and up.json()["status"] == "recebido"

    resumo = client.get("/api/v1/dashboard/resumo", headers=headers).json()
    assert resumo["totalClientes"] == 8 and len(resumo["receitaMensal"]) == 12

    lista = client.get("/api/v1/clientes", headers=headers).json()
    cid = lista[0]["id"]
    assert client.get(f"/api/v1/clientes/{cid}", headers=headers).json()["id"] == cid
    rec = client.post(f"/api/v1/clientes/{cid}/recomendacao", headers=headers).json()
    assert rec["titulo"] and rec["origem"] in ("simulacao", "ia-generativa")
    assert client.get("/api/v1/modelo", headers=headers).json()["metaAcuracia"] == 0.9
