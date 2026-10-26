import subprocess
import sys
from pathlib import Path

from fastapi.testclient import TestClient

from app.config import settings
from app.services.datalake_service import DataLakeService
from run import app

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SYNTHETIC_GENERATOR = PROJECT_ROOT / "scripts" / "generate_synthetic_clients.py"


def test_local_crm_without_external_integrations(tmp_path, monkeypatch):
    from unittest.mock import Mock

    monkeypatch.setattr(settings, "ENVIRONMENT", "test")
    monkeypatch.setattr(settings, "DATA_LAKE_BACKEND", "duckdb")
    monkeypatch.setattr(settings, "DUCKDB_PATH", str(tmp_path / "offline.duckdb"))
    monkeypatch.setattr(settings, "MLFLOW_TRACKING_URI", "")
    monkeypatch.setattr(settings, "MLFLOW_SERVING_URL", "")
    monkeypatch.setattr("ml.models.mlflow_tracker.MODEL_NAME", "")
    monkeypatch.setattr(settings, "LLM_PROVIDER", "disabled")
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "")
    monkeypatch.setattr(settings, "DEMO_EMAIL", "analyst@example.test")
    monkeypatch.setattr(settings, "DEMO_PASSWORD", "test-analyst-password")
    forbidden = Mock(side_effect=AssertionError("External integration must not be called"))
    monkeypatch.setattr("ml.models.mlflow_tracker._client", forbidden)
    monkeypatch.setattr("app.services.snowflake_service.SnowflakeDataLake.get_connection", forbidden)
    monkeypatch.setattr("app.api.v1.health._check_http_health", forbidden)
    monkeypatch.setattr("ml.inference.churn_predictor.requests.post", forbidden)

    with TestClient(app) as api:
        assert api.get("/").json()["service"] == "CRM de Alto Valor"
        assert api.get("/api/v1/health/ready").status_code == 200
        assert api.get("/api/v1/clientes").status_code in {401, 403}
        login = api.post(
            "/api/v1/auth/login",
            json={"email": "analyst@example.test", "senha": "test-analyst-password"},
        )
        assert login.status_code == 200
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
        model = api.get("/api/v1/modelo", headers=headers).json()
        assert model["status"] == "aguardando-configuracao"
        assert model["acuracia"] is None
        upload = api.post(
            "/api/v1/ingestao/clientes",
            headers=headers,
            files={"arquivo": (
                "offline.csv",
                b"id_cliente,tier,frequencia,recencia_dias,gasto_total,incidentes\n"
                b"offline-1,DIAMANTE,4,90,1200,2\n",
                "text/csv",
            )},
        )
        assert upload.status_code == 200
        clients = api.get("/api/v1/clientes", headers=headers).json()
        assert len(clients) == 1
        assert clients[0]["riscoEvasao"] is None
        assert clients[0]["id"] != "offline-1"
        recommendation = api.post(
            f"/api/v1/clientes/{clients[0]['id']}/recomendacao", headers=headers,
        ).json()
        assert recommendation["origem"] == "regras"
        assert recommendation["confianca"] is None
    forbidden.assert_not_called()


def test_upload_to_decision_recommendation_api_with_local_duckdb(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(settings, "DATA_LAKE_BACKEND", "duckdb")
    monkeypatch.setattr(settings, "DUCKDB_PATH", str(tmp_path / "e2e.duckdb"))
    monkeypatch.setattr(settings, "MLFLOW_TRACKING_URI", "http://mlflow.test")
    monkeypatch.setattr(settings, "MLFLOW_SERVING_URL", "http://serving.test/invocations")
    monkeypatch.setattr(settings, "MLFLOW_LOCAL_INFERENCE", False)
    monkeypatch.setattr(settings, "ML_INFERENCE_MODE", "local")
    monkeypatch.setattr(settings, "LLM_PROVIDER", "disabled")
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "")
    monkeypatch.setattr(settings, "DEMO_EMAIL", "analyst@example.test")
    monkeypatch.setattr(settings, "DEMO_PASSWORD", "test-analyst-password")

    csv_path = tmp_path / "synthetic_clients.csv"
    subprocess.run(
        [
            sys.executable,
            str(SYNTHETIC_GENERATOR),
            "--output",
            str(csv_path),
            "--rows",
            "8",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    csv_content = csv_path.read_bytes()
    with TestClient(app) as api:
        login = api.post(
            "/api/v1/auth/login",
            json={
                "email": "analyst@example.test",
                "senha": "test-analyst-password",
            },
        )
        assert login.status_code == 200
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

        upload = api.post(
            "/api/v1/ingestao/clientes",
            headers=headers,
            files={
                "arquivo": (
                    csv_path.name,
                    csv_content,
                    "text/csv",
                )
            },
        )
        assert upload.status_code == 200
        assert upload.json()["status"] == "recebido"
        assert "features exigidas" in upload.json()["mensagem"]
        connection = DataLakeService.get_connection()
        try:
            assert connection.execute(
                "SELECT COUNT(*) FROM bronze.raw_clients"
            ).fetchone()[0] == 8
            assert connection.execute(
                "SELECT COUNT(*) FROM silver.cleaned_clients"
            ).fetchone()[0] == 8
            assert connection.execute(
                "SELECT COUNT(*) FROM gold.client_features"
            ).fetchone()[0] == 8
            scores = connection.execute(
                "SELECT churn_score FROM gold.client_features"
            ).fetchall()
            assert all(score[0] is None for score in scores)
        finally:
            connection.close()

        clients = api.get("/api/v1/clientes", headers=headers)
        assert clients.status_code == 200
        client = next(
            item for item in clients.json() if item["tier"] == "Diamante"
        )
        assert not client["id"].startswith("synthetic-")
        assert client["riscoEvasao"] is None
        assert client["clvProjetado"] is None

        recommendation_response = api.post(
            f"/api/v1/clientes/{client['id']}/recomendacao",
            headers=headers,
        )

    assert recommendation_response.status_code == 200
    recommendation = recommendation_response.json()
    assert recommendation["tipo"] == "recuperacao-servico"
    assert recommendation["origem"] == "regras"
    assert any("Diamante -> categorias" in item for item in recommendation["regrasFidelidade"])
