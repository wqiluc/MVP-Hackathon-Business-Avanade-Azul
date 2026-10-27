import csv
import json
from pathlib import Path
from unittest.mock import MagicMock

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.services.datalake_service import DataLakeService
from app.services.ml.inference_provider import ModelInferenceError
from app.services.ml.model_contracts import CHURN_FEATURES, ChurnPrediction, ClvPrediction
from data.ingestion.file_reader import FileReader
from run import app

REAL_CSV = Path.home() / "Downloads" / "clientes_churn_limpo (1).csv"
FORBIDDEN_IN_MODEL = {
    "churn_180d", "score_churn", "churn_probabilidade", "is_churn", "clv_12m", "cpf", "data_nascimento",
}
FORBIDDEN_IN_RESPONSE = ("cliente_id", "cpf", "nome", "email", "telefone")
SAMPLE_ROWS = 20

pytestmark = pytest.mark.skipif(not REAL_CSV.exists(), reason="local real CSV not available")


@pytest.fixture
def real_sample(tmp_path):
    """Temporary copy with a few real rows; the original is never modified or stored in the repo."""
    with REAL_CSV.open(newline="", encoding="utf-8") as handle:
        reader = csv.reader(handle)
        header = next(reader)
        rows = [row for _, row in zip(range(SAMPLE_ROWS), reader)]
    target = tmp_path / "sample.csv"
    with target.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(header)
        writer.writerows(rows)
    return target, header


def _meta():
    return dict(model_name="m", model_version="1", source="local", timestamp=pd.Timestamp.now(tz="UTC"))


def _mock_services(monkeypatch, churn=None, clv=None):
    sent = {}

    def churn_fn(features):
        sent["churn"] = features
        if churn is ModelInferenceError:
            raise ModelInferenceError("unavailable")
        return [ChurnPrediction(score=0.25 + 0.5 * (i % 2), **_meta()) for i, _ in enumerate(features)]

    def clv_fn(features):
        sent["clv"] = features
        if clv is ModelInferenceError:
            raise ModelInferenceError("unavailable")
        return [ClvPrediction(value=100.0 * (i + 1), **_meta()) for i, _ in enumerate(features)]

    monkeypatch.setattr("app.services.ml.churn_service.ChurnService", lambda: MagicMock(predict_many=churn_fn))
    monkeypatch.setattr("app.services.ml.clv_service.ClvService", lambda: MagicMock(predict_many=clv_fn))
    return sent


def test_real_dataset_is_ml_features_52_and_target_pii_removed(real_sample):
    path, header = real_sample
    assert len(header) == 64 and "churn_180d" in header
    frame = FileReader.read_file(str(path), "csv")
    assert frame.attrs["ingestion_contract"] == "ML_FEATURES_52"
    assert len(frame.columns) == 52 and list(frame.columns) == list(CHURN_FEATURES)
    assert len(frame) == SAMPLE_ROWS
    assert not FORBIDDEN_IN_MODEL & set(frame.columns)


def test_scoring_summary_is_aggregate_only_and_correct(real_sample, monkeypatch):
    path, _ = real_sample
    sent = _mock_services(monkeypatch)
    result = DataLakeService.score_ml_features(FileReader.read_file(str(path), "csv"))
    assert result["status"] == "scored_not_persisted"
    assert result["ingestion_contract"] == "ML_FEATURES_52"
    assert result["processed_rows"] == SAMPLE_ROWS
    for model in ("churn", "clv"):
        assert not FORBIDDEN_IN_MODEL & set(sent[model][0])
    summary = result["scoring_summary"]
    assert summary["clv_mean"] == pytest.approx(sum(100.0 * (i + 1) for i in range(SAMPLE_ROWS)) / SAMPLE_ROWS)
    assert summary["model_versions"] == {"churn": "m:1", "clv": "m:1"}
    serialized = json.dumps(result).lower()
    assert not any(word in serialized for word in FORBIDDEN_IN_RESPONSE)


def test_clv_unavailable_keeps_churn(real_sample, monkeypatch):
    path, _ = real_sample
    _mock_services(monkeypatch, clv=ModelInferenceError)
    result = DataLakeService.score_ml_features(FileReader.read_file(str(path), "csv"))
    assert result["scoring_status"] == "partial"
    assert result["scoring_summary"]["clv_mean"] is None
    assert result["scoring_summary"]["churn_score_mean"] is not None
    assert "clv" not in result["scoring_summary"]["model_versions"]


def test_churn_unavailable_keeps_clv_without_fallback(real_sample, monkeypatch):
    path, _ = real_sample
    _mock_services(monkeypatch, churn=ModelInferenceError)
    result = DataLakeService.score_ml_features(FileReader.read_file(str(path), "csv"))
    assert result["scoring_status"] == "partial"
    assert result["scoring_summary"]["churn_score_mean"] is None
    assert result["scoring_summary"]["churn_score_max"] is None
    assert result["scoring_summary"]["clv_mean"] is not None


def test_both_unavailable(real_sample, monkeypatch):
    path, _ = real_sample
    _mock_services(monkeypatch, churn=ModelInferenceError, clv=ModelInferenceError)
    result = DataLakeService.score_ml_features(FileReader.read_file(str(path), "csv"))
    assert result["scoring_status"] == "unavailable"
    assert result["status"] == "scored_not_persisted"


@pytest.fixture
def api(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "ENVIRONMENT", "test")
    monkeypatch.setattr(settings, "DATA_LAKE_BACKEND", "duckdb")
    monkeypatch.setattr(settings, "DUCKDB_PATH", str(tmp_path / "e2e.duckdb"))
    monkeypatch.setattr(settings, "LLM_PROVIDER", "disabled")
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "")
    monkeypatch.setattr(settings, "DEMO_EMAIL", "analyst@example.test")
    monkeypatch.setattr(settings, "DEMO_PASSWORD", "test-analyst-password")
    with TestClient(app) as client:
        login = client.post(
            "/api/v1/auth/login",
            json={"email": "analyst@example.test", "senha": "test-analyst-password"},
        )
        client.headers.update({"Authorization": f"Bearer {login.json()['access_token']}"})
        yield client


def _upload(api, name, content):
    return api.post("/api/v1/ingestao/clientes", files={"arquivo": (name, content, "text/csv")})


def test_api_ml_upload_scores_and_does_not_persist(api, real_sample, monkeypatch):
    path, _ = real_sample
    _mock_services(monkeypatch)
    response = _upload(api, "ml.csv", path.read_bytes())
    assert response.status_code == 200
    body = response.json()
    assert body["ingestion_contract"] == "ML_FEATURES_52"
    assert isinstance(body["scoring_summary"], dict)
    assert "Churn e CLV calculados." in body["mensagem"]
    assert not any(word in json.dumps(body).lower() for word in FORBIDDEN_IN_RESPONSE)
    assert api.get("/api/v1/clientes").json() == []


def test_api_ml_upload_with_clv_unavailable_is_not_500(api, real_sample, monkeypatch):
    path, _ = real_sample
    _mock_services(monkeypatch, clv=ModelInferenceError)
    response = _upload(api, "ml.csv", path.read_bytes())
    assert response.status_code == 200
    assert response.json()["scoring_summary"]["clv_mean"] is None
    assert "Churn calculado; CLV indisponível." in response.json()["mensagem"]
    assert "oficiais" not in response.json()["mensagem"]
    assert api.get("/api/v1/clientes").json() == []


def test_api_ml_upload_with_churn_unavailable_is_not_500(api, real_sample, monkeypatch):
    path, _ = real_sample
    _mock_services(monkeypatch, churn=ModelInferenceError)
    response = _upload(api, "ml.csv", path.read_bytes())
    assert response.status_code == 200
    assert response.json()["scoring_summary"]["churn_score_mean"] is None
    assert "CLV calculado; Churn indisponível." in response.json()["mensagem"]
    assert api.get("/api/v1/clientes").json() == []


def test_api_invalid_file_is_rejected_with_contracts(api):
    response = _upload(api, "bad.csv", b"foo,bar,baz\n1,2,3\n")
    assert response.status_code == 422
    text = json.dumps(response.json())
    assert "CRM_CANONICAL" in text and "ML_FEATURES_52" in text


def test_api_crm_canonical_end_to_end_with_null_scores(api):
    content = (
        b"id_cliente,tier,frequencia,recencia_dias,gasto_total,incidentes\n"
        b"c-1,DIAMANTE,4,30,1200,1\n"
    )
    response = _upload(api, "crm.csv", content)
    assert response.status_code == 200
    assert response.json()["ingestion_contract"] == "CRM_CANONICAL"
    clients = api.get("/api/v1/clientes").json()
    assert len(clients) == 1
    assert clients[0]["riscoEvasao"] is None and clients[0]["clvProjetado"] is None
    assert len(api.get("/api/v1/clientes", params={"tier": "Diamante"}).json()) == 1
    assert api.get("/api/v1/clientes", params={"tier": "Básico"}).json() == []
    assert api.get(f"/api/v1/clientes/{clients[0]['id']}").status_code == 200
    recommendation = api.post(f"/api/v1/clientes/{clients[0]['id']}/recomendacao")
    assert recommendation.status_code == 200
    assert recommendation.json()["origem"] == "regras"


def test_value_at_risk_is_unavailable_without_clv():
    from ai.agents.workflow import decision_agent, query_manager_agent

    def run(clv):
        state = {
            "client_identifier": "x", "churn_score": 0.6, "clv_12m": clv, "frequency": 1,
            "total_spend": 1000.0, "flight_incidents": 0, "incident_type": None,
            "tier": "Safira", "value_at_risk": 0.0, "graph_rag_context": {"graph_relations": []},
            "decision": {}, "audit_status": "",
        }
        state = query_manager_agent(state)
        return decision_agent(state)["decision"]["evidence"]

    assert "Valor em risco: indisponível" in run(None)
    assert not any("R$ 0.00" in e and "risco" in e for e in run(None))
    assert any(e.startswith("Valor em risco calculado: R$") for e in run(5000.0))
