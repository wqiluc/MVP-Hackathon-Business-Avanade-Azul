import ast
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import duckdb
import pandas as pd
import pytest
from fastapi.testclient import TestClient
from app.services.crm_service import gerar_recomendacao
from app.services.datalake_service import DataLakeService
from run import app

client = TestClient(app)


def _authenticated_headers():
    login = client.post("/api/v1/auth/login", json={"username": "analista_azul", "password": "azul123"})
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


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


def test_ml_api_does_not_import_mlflow():
    api_path = Path(__file__).parents[1] / "app" / "api" / "v1" / "ml.py"
    tree = ast.parse(api_path.read_text(encoding="utf-8"))

    imported_modules = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.append(node.module)

    assert not any(module == "mlflow" or module.startswith("mlflow.") for module in imported_modules)


def test_upload_api_does_not_import_or_call_datalake_service():
    api_path = Path(__file__).parents[1] / "app" / "api" / "v1" / "uploads.py"
    tree = ast.parse(api_path.read_text(encoding="utf-8"))

    imported_modules = []
    called_attributes = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.append(node.module)
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            called_attributes.append(node.func.attr)

    assert not any("datalake_service" in module or "DataLakeService" in module for module in imported_modules)
    assert "process_ingestion" not in called_attributes


def test_datalake_file_reader_delegates_to_file_reader():
    expected = pd.DataFrame({"id_cliente": [1]})

    with patch(
        "app.services.datalake_service.FileReader.read_file",
        return_value=expected,
    ) as read_file:
        result = DataLakeService._ler_arquivo("clients.csv", "csv")

    assert result is expected
    read_file.assert_called_once_with("clients.csv", "csv")


def test_score_gold_delegates_persistence_to_duckdb_adapter():
    conn = duckdb.connect(":memory:")
    conn.execute("CREATE SCHEMA gold")
    conn.execute(
        "CREATE TABLE gold.client_features AS "
        "SELECT 'AZ-test' AS client_identifier, 3 AS frequency"
    )

    with patch("app.services.inference_service.predict_churn", return_value=[0.425]) as predict:
        DataLakeService._score_gold(conn)

    result = conn.execute("SELECT * FROM gold.client_features").fetchdf()
    conn.close()

    assert result.to_dict(orient="records") == [
        {"client_identifier": "AZ-test", "frequency": 3, "churn_score": 0.425}
    ]
    predict.assert_called_once()


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


def test_model_endpoint_returns_existing_mlflow_run_contract():
    started = datetime(2026, 10, 17, 12, 30, tzinfo=timezone.utc)
    runs = pd.DataFrame([{
        "run_id": "12345678abcdefgh",
        "metrics.accuracy": 0.875,
        "start_time": started,
    }])

    with patch("app.services.ml_service.mlflow.search_runs", return_value=runs) as search_runs:
        response = client.get("/api/v1/modelo", headers=_authenticated_headers())

    assert response.status_code == 200
    assert response.json() == {
        "nome": "Modelo de evasão (RandomForest)",
        "plataforma": "MLflow",
        "metaAcuracia": 0.9,
        "versao": "12345678",
        "status": "em-producao",
        "acuracia": 0.875,
        "auc": None,
        "treinadoEm": started.isoformat(),
    }
    search_runs.assert_called_once_with(
        experiment_names=["Azul_CRM_Churn_Prediction"],
        order_by=["attributes.start_time DESC"],
        max_results=1,
    )


def test_model_endpoint_returns_fallback_when_mlflow_has_no_runs():
    with patch("app.services.ml_service.mlflow.search_runs", return_value=pd.DataFrame()):
        response = client.get("/api/v1/modelo", headers=_authenticated_headers())

    assert response.status_code == 200
    assert response.json() == {
        "nome": "Modelo de evasão (RandomForest)",
        "plataforma": "MLflow",
        "metaAcuracia": 0.9,
        "versao": "—",
        "status": "aguardando-registro",
        "acuracia": None,
        "auc": None,
        "treinadoEm": None,
    }


def test_model_endpoint_returns_fallback_when_mlflow_query_raises():
    with patch("app.services.ml_service.mlflow.search_runs", side_effect=RuntimeError("MLflow unavailable")):
        response = client.get("/api/v1/modelo", headers=_authenticated_headers())

    assert response.status_code == 200
    assert response.json() == {
        "nome": "Modelo de evasão (RandomForest)",
        "plataforma": "MLflow",
        "metaAcuracia": 0.9,
        "versao": "—",
        "status": "aguardando-registro",
        "acuracia": None,
        "auc": None,
        "treinadoEm": None,
    }


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


def test_legacy_upload_route_accepts_file_field(monkeypatch):
    with patch(
        "app.services.upload_service.DataLakeService.process_ingestion",
        return_value={"status": "success", "processed_rows": 2, "layers": ["bronze", "silver", "gold"]},
    ):
        response = client.post(
            "/api/v1/data/ingest",
            headers=_authenticated_headers(),
            files={"file": ("customers.csv", b"valid csv payload", "text/csv")},
        )

    assert response.status_code == 200
    assert response.json()["details"]["processed_rows"] == 2


def test_upload_rejects_invalid_extension_with_existing_response():
    response = client.post(
        "/api/v1/ingestao/clientes",
        headers=_authenticated_headers(),
        files={"arquivo": ("customers.txt", b"payload", "text/plain")},
    )

    assert response.status_code == 400
    assert response.json()["message"] == "Formato não permitido. Envie ficheiros Excel (.xlsx/.xls), CSV ou JSON."


def test_empty_upload_preserves_existing_http_500_behavior():
    response = client.post(
        "/api/v1/ingestao/clientes",
        headers=_authenticated_headers(),
        files={"arquivo": ("empty.csv", b"", "text/csv")},
    )

    assert response.status_code == 500
    assert response.json()["message"] == "Falha ao guardar o ficheiro temporário: 400: O ficheiro enviado está vazio."


def test_upload_with_invalid_data_returns_422():
    response = client.post(
        "/api/v1/ingestao/clientes",
        headers=_authenticated_headers(),
        files={"arquivo": ("invalid.csv", b"wrong,columns\n1,2\n", "text/csv")},
    )

    assert response.status_code == 422
    assert response.json()["message"] == (
        "Colunas obrigatórias ausentes: frequencia, gasto_total, id_cliente, incidentes, recencia_dias, tier"
    )


def test_datalake_value_error_returns_http_422():
    with patch(
        "app.services.upload_service.DataLakeService.process_ingestion",
        side_effect=ValueError("ingestion rejected"),
    ):
        response = client.post(
            "/api/v1/ingestao/clientes",
            headers=_authenticated_headers(),
            files={"arquivo": ("customers.csv", b"payload", "text/csv")},
        )

    assert response.status_code == 422
    assert response.json()["message"] == "ingestion rejected"


def test_upload_save_failure_preserves_http_500(monkeypatch):
    def fail_to_open(*args, **kwargs):
        raise OSError("disk unavailable")

    monkeypatch.setattr("builtins.open", fail_to_open)
    response = client.post(
        "/api/v1/ingestao/clientes",
        headers=_authenticated_headers(),
        files={"arquivo": ("customers.csv", b"payload", "text/csv")},
    )

    assert response.status_code == 500
    assert response.json()["message"] == "Falha ao guardar o ficheiro temporário: disk unavailable"


def test_upload_temp_file_is_removed_when_ingestion_raises(tmp_path, monkeypatch):
    temp_file = tmp_path / "temporary-upload.csv"

    async def save_temp_file(_file):
        temp_file.write_bytes(b"payload")
        return str(temp_file)

    monkeypatch.setattr("app.services.upload_service.UploadService.save_temp_file", staticmethod(save_temp_file))
    with patch(
        "app.services.upload_service.DataLakeService.process_ingestion",
        side_effect=ValueError("ingestion rejected"),
    ):
        response = client.post(
            "/api/v1/ingestao/clientes",
            headers=_authenticated_headers(),
            files={"arquivo": ("customers.csv", b"payload", "text/csv")},
        )

    assert response.status_code == 422
    assert not temp_file.exists()
