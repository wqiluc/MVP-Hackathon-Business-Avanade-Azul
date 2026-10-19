from fastapi.testclient import TestClient

from app.config import settings
from run import app


def test_upload_to_decision_recommendation_api_with_local_duckdb(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(settings, "DATA_LAKE_BACKEND", "duckdb")
    monkeypatch.setattr(settings, "DUCKDB_PATH", str(tmp_path / "e2e.duckdb"))
    monkeypatch.setattr(settings, "MLFLOW_TRACKING_URI", "http://mlflow.test")
    monkeypatch.setattr(settings, "MLFLOW_SERVING_URL", "http://serving.test/invocations")
    monkeypatch.setattr(settings, "MLFLOW_LOCAL_INFERENCE", False)
    monkeypatch.setattr(settings, "LLM_PROVIDER", "disabled")
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "")
    monkeypatch.setattr(settings, "DEMO_EMAIL", "analyst@example.test")
    monkeypatch.setattr(settings, "DEMO_PASSWORD", "test-analyst-password")

    monkeypatch.setattr(
        "ml.models.mlflow_tracker.configure_tracking",
        lambda _uri: None,
    )
    monkeypatch.setattr(
        "ml.models.mlflow_tracker.get_active_churn_model",
        lambda: object(),
    )
    predictions = []

    def predict_churn(gold):
        predictions.append(gold.copy())
        return [0.82] * len(gold)

    monkeypatch.setattr(
        "app.services.inference_service.predict_churn",
        predict_churn,
    )

    csv_content = (
        "id_cliente,tier,frequencia,recencia_dias,gasto_total,incidentes\n"
        "customer-e2e-1,DIAMANTE,10,30,50000,2\n"
        "customer-e2e-2,SAFIRA,5,80,15000,0\n"
    )
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
                    "clients.csv",
                    csv_content.encode("utf-8"),
                    "text/csv",
                )
            },
        )
        assert upload.status_code == 200
        assert upload.json()["status"] == "recebido"
        assert len(predictions) == 1
        assert len(predictions[0]) == 2
        assert "customer-e2e-1" not in predictions[0]["client_identifier"].to_list()

        clients = api.get("/api/v1/clientes", headers=headers)
        assert clients.status_code == 200
        client = next(
            item
            for item in clients.json()
            if item["tier"] == "Diamante" and item["riscoEvasao"] == 0.82
        )
        assert not client["id"].startswith("customer-")

        recommendation_response = api.post(
            f"/api/v1/clientes/{client['id']}/recomendacao",
            headers=headers,
        )

    assert recommendation_response.status_code == 200
    recommendation = recommendation_response.json()
    assert recommendation["tipo"] == "recuperacao-servico"
    assert recommendation["origem"] == "regras"
    assert any("Diamante -> categorias" in item for item in recommendation["regrasFidelidade"])
    assert any("high_risk_flag" in item for item in recommendation["justificativa"])
