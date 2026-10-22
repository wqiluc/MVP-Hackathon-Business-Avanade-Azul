import ast
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import duckdb
import pandas as pd
import pytest
from fastapi.testclient import TestClient
from app.config import settings
from app.services.crm_service import gerar_recomendacao
from app.services.datalake_service import DataLakeService
from run import app

client = TestClient(app)

TEST_EMAIL = "analyst@example.test"
TEST_PASSWORD = "test-analyst-password"
ADMIN_EMAIL = "admin@example.test"
ADMIN_PASSWORD = "test-admin-password"


@pytest.fixture(autouse=True)
def configure_test_auth(monkeypatch):
    monkeypatch.setattr(settings, "MLFLOW_TRACKING_URI", "http://mlflow.test")
    monkeypatch.setattr("ml.models.mlflow_tracker.MODEL_NAME", "crm-test-model")
    monkeypatch.setattr(settings, "DEMO_EMAIL", TEST_EMAIL)
    monkeypatch.setattr(settings, "DEMO_PASSWORD", TEST_PASSWORD)
    monkeypatch.setattr(settings, "ADMIN_EMAIL", ADMIN_EMAIL)
    monkeypatch.setattr(settings, "ADMIN_PASSWORD", ADMIN_PASSWORD)
    monkeypatch.setattr(settings, "MLFLOW_SERVING_URL", "")
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "")
    monkeypatch.setattr(settings, "LLM_PROVIDER", "disabled")


def _authenticated_headers():
    login = client.post("/api/v1/auth/login", json={"email": TEST_EMAIL, "senha": TEST_PASSWORD})
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


def _admin_headers():
    login = client.post("/api/v1/auth/login", json={"email": ADMIN_EMAIL, "senha": ADMIN_PASSWORD})
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

    with (
        patch("ml.models.mlflow_tracker.configure_tracking"),
        patch("ml.models.mlflow_tracker.get_active_churn_model", return_value=object()),
        patch("app.services.inference_service.predict_churn", return_value=[0.425]) as predict,
    ):
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
    res = client.post("/api/v1/auth/login", json={"email": TEST_EMAIL, "senha": TEST_PASSWORD})
    assert res.status_code == 200
    assert "access_token" in res.json()


def test_admin_login_and_role_restriction():
    response = client.post(
        "/api/v1/auth/login",
        json={"email": ADMIN_EMAIL, "senha": ADMIN_PASSWORD},
    )
    assert response.status_code == 200
    assert response.json()["role"] == "ADMIN"

    denied = client.post("/api/v1/modelo/train", headers=_authenticated_headers())
    assert denied.status_code == 403


def test_login_rejects_invalid_credentials_with_existing_contract():
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "invalid@example.com", "senha": "invalid"},
    )

    assert response.status_code == 401
    assert response.json()["message"] == "Credenciais inválidas. Verifique usuário e senha."


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
    login_res = client.post("/api/v1/auth/login", json={"email": TEST_EMAIL, "senha": TEST_PASSWORD})
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
    assert data["audit_status"] == "WORKFLOW_COMPLETE"


def test_current_client_analysis_endpoint():
    login = client.post("/api/v1/auth/login", json={"email": TEST_EMAIL, "senha": TEST_PASSWORD})
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
    assert response.json()["audit_status"] == "WORKFLOW_COMPLETE"


def test_recommendation_falls_back_when_agent_workflow_fails():
    base_action = {"tipo": "simulacao", "titulo": "Ação por regras"}
    cliente = {
        "proximaAcao": base_action,
        "id": "AZ-test",
        "_churn_score": 0.4,
        "voos12m": 10,
        "receita12m": 50000.0,
        "_flight_incidents": 1,
        "_incident_type": "Downgrade Involuntário",
        "tier": "Safira",
    }

    with patch("app.services.crm_service.invoke_agent_workflow", side_effect=RuntimeError("workflow error")):
        result = gerar_recomendacao(cliente)
    assert result["titulo"].startswith(base_action["titulo"])
    assert result["origem"] == "regras"
    assert "política não verificada" in result["titulo"]
    assert "Demonstração" in result["mensagem"]


def test_recommendation_transmits_canonical_crm_values_to_workflow():
    cliente = {
        "proximaAcao": {
            "tipo": "bonus-pontos",
            "titulo": "Ação por regras",
            "justificativa": [],
            "canal": "E-mail",
            "mensagem": "Mensagem",
            "regrasFidelidade": [],
            "confianca": None,
            "origem": "simulacao",
            "impactoEstimado": {"reducaoRiscoPp": None, "receitaProtegida": None},
        },
        "id": "AZ-test",
        "_churn_score": 0.4,
        "voos12m": 10,
        "receita12m": 50000.0,
        "_flight_incidents": 5,
        "_incident_type": "Downgrade Involuntário",
        "tier": "Diamante",
    }
    workflow_result = {
        "decision": {
            "action_code": "recuperacao-servico",
            "strategy": "Revisão de atendimento",
            "reasoning": "Política aplicável.",
            "evidence": ["Downgrade Involuntário -> revisão humana necessária"],
            "proposal": {
                "voucher_value": 0.0,
                "benefit": "Validar o caso com um analista.",
                "bonus_points": 0,
            },
        },
        "graph_rag_context": {
            "tier": "Diamante",
            "incident_type": "Downgrade Involuntário",
            "graph_relations": ["Downgrade Involuntário -> revisão humana necessária"],
            "policy_context": "Regra aplicável.",
        },
        "audit_status": "WORKFLOW_COMPLETE",
    }
    with patch(
        "app.services.crm_service.invoke_agent_workflow",
        return_value=workflow_result,
    ) as invoke:
        result = gerar_recomendacao(cliente)

    state = invoke.call_args.args[0]
    assert state["churn_score"] == 0.4
    assert state["tier"] == "Diamante"
    assert state["flight_incidents"] == 5
    assert state["incident_type"] == "Downgrade Involuntário"
    assert "churn_risk" not in state
    assert result["tipo"] == "recuperacao-servico"
    assert result["origem"] == "regras"
    assert "política não verificada" in result["titulo"]
    assert "Demonstração" in result["mensagem"]
    assert "Regra aplicável." in result["regrasFidelidade"]


@pytest.mark.parametrize(
    "reason",
    [
        "timeout",
        "connection_error",
        "rate_limit",
        "quota_billing",
        "api_status_error",
        "invalid_response",
    ],
)
def test_openai_failure_marks_rules_fallback_as_unavailable_llm(monkeypatch, reason):
    from ai.llm.openai_recommendation import OpenAIRecommendationError

    monkeypatch.setattr(settings, "LLM_PROVIDER", "openai")
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "test-key")
    cliente = {
        "proximaAcao": {
            "tipo": "comunicacao",
            "titulo": "Contato informativo",
            "justificativa": [],
            "canal": "App",
            "mensagem": "Contato",
            "regrasFidelidade": [],
            "confianca": None,
            "origem": "simulacao",
            "impactoEstimado": {"reducaoRiscoPp": None, "receitaProtegida": None},
        },
        "id": "AZ-test",
        "_churn_score": 0.2,
        "voos12m": 2,
        "receita12m": 1000.0,
        "_flight_incidents": 0,
        "_incident_type": None,
        "tier": "Básico",
    }

    with patch(
        "ai.llm.openai_recommendation.OpenAIRecommendationService.recommend",
        side_effect=OpenAIRecommendationError(reason),
    ):
        result = gerar_recomendacao(cliente)

    assert result["origem"] == "llm-indisponivel"


def test_missing_openai_key_uses_normal_rules_fallback(monkeypatch):
    monkeypatch.setattr(settings, "LLM_PROVIDER", "openai")
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "")
    cliente = {
        "proximaAcao": {
            "tipo": "comunicacao",
            "titulo": "Contato informativo",
            "justificativa": [],
            "canal": "App",
            "mensagem": "Contato",
            "regrasFidelidade": [],
            "confianca": None,
            "origem": "simulacao",
            "impactoEstimado": {"reducaoRiscoPp": None, "receitaProtegida": None},
        },
        "id": "AZ-test",
        "_churn_score": 0.2,
        "voos12m": 2,
        "receita12m": 1000.0,
        "_flight_incidents": 0,
        "_incident_type": None,
        "tier": "Básico",
    }

    with patch(
        "ai.llm.openai_recommendation.OpenAIRecommendationService.recommend",
    ) as recommend:
        result = gerar_recomendacao(cliente)

    assert result["origem"] == "regras"
    recommend.assert_not_called()


def test_openai_failure_preserves_decision_agent_action(monkeypatch):
    from ai.llm.openai_recommendation import OpenAIRecommendationError

    monkeypatch.setattr(settings, "LLM_PROVIDER", "openai")
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "test-key")
    cliente = {
        "proximaAcao": {
            "tipo": "comunicacao",
            "titulo": "Contato informativo",
            "justificativa": [],
            "canal": "App",
            "mensagem": "Contato",
            "regrasFidelidade": [],
            "confianca": None,
            "origem": "simulacao",
            "impactoEstimado": {"reducaoRiscoPp": None, "receitaProtegida": None},
        },
        "id": "AZ-test",
        "_churn_score": 0.8,
        "voos12m": 10,
        "receita12m": 50000.0,
        "_flight_incidents": 2,
        "_incident_type": "Incidente",
        "tier": "Diamante",
    }
    decision = {
        "action_code": "recuperacao-servico",
        "strategy": "Revisão humana de incidente",
        "reasoning": "O incidente precisa ser revisado.",
        "evidence": ["Incidentes: 2"],
        "proposal": {
            "voucher_value": 0.0,
            "benefit": "Validar o caso com um analista.",
            "bonus_points": 0,
        },
    }
    workflow = {
        "decision": decision,
        "graph_rag_context": {
            "policy_context": "Premissa ilustrativa.",
            "graph_relations": [],
            "policies_verified": False,
        },
    }

    with (
        patch("app.services.crm_service.invoke_agent_workflow", return_value=workflow),
        patch(
            "ai.llm.openai_recommendation.OpenAIRecommendationService.recommend",
            side_effect=OpenAIRecommendationError("quota_billing"),
        ),
    ):
        result = gerar_recomendacao(cliente)

    assert result["tipo"] == decision["action_code"]
    assert result["titulo"].startswith(decision["strategy"])
    assert result["origem"] == "llm-indisponivel"
    assert decision["reasoning"] in result["justificativa"]


def test_openai_personalizes_text_without_replacing_decision_action(monkeypatch):
    monkeypatch.setattr(settings, "LLM_PROVIDER", "openai")
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "test-key")
    cliente = {
        "proximaAcao": {
            "tipo": "comunicacao",
            "titulo": "Contato informativo",
            "justificativa": [],
            "canal": "App",
            "mensagem": "Contato",
            "regrasFidelidade": [],
            "confianca": None,
            "origem": "simulacao",
            "impactoEstimado": {"reducaoRiscoPp": None, "receitaProtegida": None},
        },
        "id": "AZ-test",
        "_churn_score": 0.8,
        "voos12m": 10,
        "receita12m": 50000.0,
        "_flight_incidents": 2,
        "_incident_type": "Incidente",
        "tier": "Diamante",
    }
    decision = {
        "action_code": "recuperacao-servico",
        "strategy": "Revisão humana de incidente",
        "reasoning": "Dois incidentes precisam ser revisados.",
        "evidence": ["Incidentes: 2"],
        "proposal": {
            "voucher_value": 0.0,
            "benefit": "Validar o caso com um analista.",
            "bonus_points": 0,
        },
    }
    workflow = {
        "decision": decision,
        "graph_rag_context": {
            "policy_context": "Premissa ilustrativa.",
            "graph_relations": [],
            "policies_verified": False,
        },
    }
    generated = SimpleNamespace(
        action_code="comunicacao",
        strategy="Mensagem alternativa",
        reasoning="Texto personalizado.",
        channel="App",
        message="Texto de contato.",
        benefit="Consultar opções.",
        bonus_points=0,
        voucher_value=0.0,
        evidence=["Evidência da resposta."],
    )

    with (
        patch("app.services.crm_service.invoke_agent_workflow", return_value=workflow),
        patch(
            "ai.llm.openai_recommendation.OpenAIRecommendationService.recommend",
            return_value=generated,
        ),
    ):
        result = gerar_recomendacao(cliente)

    assert result["tipo"] == decision["action_code"]
    assert result["titulo"].startswith(decision["strategy"])
    assert result["mensagem"].endswith(generated.message)
    assert result["origem"] == "llm"


def test_model_endpoint_returns_existing_mlflow_run_contract():
    started = datetime(2026, 10, 17, 12, 30, tzinfo=timezone.utc)
    active = SimpleNamespace(
        model_name="crm-test-model",
        model_version="3",
        alias="champion",
        run_id="12345678abcdefgh",
        status="READY",
        metrics={"accuracy": 0.875},
        start_time=int(started.timestamp() * 1000),
    )

    with patch(
        "app.services.ml_service.get_active_churn_model",
        return_value=active,
    ) as get_active_model:
        response = client.get("/api/v1/modelo", headers=_authenticated_headers())

    assert response.status_code == 200
    assert response.json() == {
        "nome": "crm-test-model",
        "plataforma": "MLflow",
        "metaAcuracia": None,
        "versao": "3",
        "status": "aguardando-serving",
        "acuracia": 0.875,
        "auc": None,
        "treinadoEm": started.isoformat(),
    }
    get_active_model.assert_called_once_with()


def test_model_endpoint_returns_fallback_when_mlflow_has_no_runs():
    with patch("app.services.ml_service.get_active_churn_model", return_value=None):
        response = client.get("/api/v1/modelo", headers=_authenticated_headers())

    assert response.status_code == 200
    assert response.json() == {
        "nome": "Classificador high_risk_flag (RandomForest)",
        "plataforma": "MLflow",
        "metaAcuracia": None,
        "versao": "—",
        "status": "aguardando-registro",
        "acuracia": None,
        "auc": None,
        "treinadoEm": None,
    }


@pytest.mark.parametrize("missing", ["tracking", "model"])
def test_model_endpoint_without_configuration_does_not_query_registry(monkeypatch, missing):
    if missing == "tracking":
        monkeypatch.setattr(settings, "MLFLOW_TRACKING_URI", "")
    else:
        monkeypatch.setattr("ml.models.mlflow_tracker.MODEL_NAME", "")
    with patch("app.services.ml_service.get_active_churn_model") as registry:
        response = client.get("/api/v1/modelo", headers=_authenticated_headers())
    assert response.status_code == 200
    assert response.json()["status"] == "aguardando-configuracao"
    assert response.json()["acuracia"] is None
    assert response.json()["versao"] == "—"
    registry.assert_not_called()


def test_model_endpoint_returns_fallback_when_mlflow_query_raises():
    with patch(
        "app.services.ml_service.get_active_churn_model",
        side_effect=RuntimeError("MLflow unavailable"),
    ):
        unavailable_client = TestClient(app, raise_server_exceptions=False)
        response = unavailable_client.get(
            "/api/v1/modelo",
            headers=_authenticated_headers(),
        )

    assert response.status_code == 500


def test_front_contract_flow(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "app.config.settings.DUCKDB_PATH",
        str(tmp_path / "front-contract.duckdb"),
    )
    monkeypatch.setattr("app.config.settings.DATA_LAKE_BACKEND", "duckdb")

    csv = tmp_path / "base.csv"
    csv.write_text(
        "id_cliente,tier,frequencia,recencia_dias,gasto_total,incidentes\n"
        + "\n".join(f"{i},DIAMANTE,{10 + i},{i * 10},{5000 * i},{i % 3}" for i in range(1, 9))
    )
    with (
        patch("ml.models.mlflow_tracker.configure_tracking"),
        patch("ml.models.mlflow_tracker.get_active_churn_model", return_value=None),
        TestClient(app) as test_client,
    ):
        res = test_client.post(
            "/api/v1/auth/login",
            json={"email": TEST_EMAIL, "senha": TEST_PASSWORD},
        )
        assert res.status_code == 200
        body = res.json()
        assert body["token"] and body["usuario"]["perfil"] == "analista" and body["expiraEm"]
        headers = {"Authorization": f"Bearer {body['token']}"}

        with open(csv, "rb") as f:
            up = test_client.post(
                "/api/v1/ingestao/clientes",
                headers=headers,
                files={"arquivo": ("base.csv", f)},
            )
        assert up.status_code == 200 and up.json()["status"] == "recebido"

        resumo = test_client.get("/api/v1/dashboard/resumo", headers=headers).json()
        assert resumo["totalClientes"] == 8 and len(resumo["receitaMensal"]) == 12

        lista = test_client.get("/api/v1/clientes", headers=headers).json()
        cid = lista[0]["id"]
        assert test_client.get(f"/api/v1/clientes/{cid}", headers=headers).json()["id"] == cid
        rec = test_client.post(
            f"/api/v1/clientes/{cid}/recomendacao",
            headers=headers,
        ).json()
        assert rec["titulo"] and rec["origem"] == "regras"
        cliente_detail = test_client.get(
            f"/api/v1/clientes/{cid}", headers=headers
        ).json()
        assert not any(
            key.startswith("_") for key in cliente_detail
        )
        with patch("app.services.ml_service.get_active_churn_model", return_value=None):
            assert test_client.get("/api/v1/modelo", headers=headers).json()["metaAcuracia"] is None


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


def test_current_ingestion_alias_preserves_response_model():
    summary = {"status": "success", "processed_rows": 2, "layers": ["bronze", "silver", "gold"]}
    with patch("app.services.upload_service.UploadService.process_upload", return_value=(summary, 12)):
        response = client.post(
            "/api/v1/ingestao/ingest",
            headers=_authenticated_headers(),
            files={"file": ("customers.csv", b"valid csv payload", "text/csv")},
        )

    assert response.status_code == 200
    assert response.json() == {
        "message": "Base de dados processada com sucesso nas camadas Bronze, Silver e Gold!",
        "details": summary,
    }


def test_model_training_endpoint_preserves_response_schema():
    training_result = {
        "run_id": "characterization-run-id",
        "accuracy": 0.875,
        "precision": 0.8,
        "recall": 0.9,
        "status": "Modelo registrado no MLflow com sucesso",
    }
    with patch(
        "app.api.v1.ml.train_and_register_churn_model",
        return_value=training_result,
    ):
        response = client.post("/api/v1/modelo/train", headers=_admin_headers())

    assert response.status_code == 200
    assert response.json() == training_result


def test_health_endpoint_is_available_without_authentication():
    response = client.get("/api/v1/health/")

    assert response.status_code == 200
    assert response.json() == {
        "status": "online",
        "service": "CRM de Alto Valor",
        "version": "2.0.0",
    }


def test_upload_rejects_invalid_extension_with_existing_response():
    response = client.post(
        "/api/v1/ingestao/clientes",
        headers=_authenticated_headers(),
        files={"arquivo": ("customers.txt", b"payload", "text/plain")},
    )

    assert response.status_code == 400
    assert response.json()["message"] == "Formato não permitido. Envie ficheiros Excel (.xlsx/.xls), CSV ou JSON."


def test_empty_upload_returns_clear_http_400():
    response = client.post(
        "/api/v1/ingestao/clientes",
        headers=_authenticated_headers(),
        files={"arquivo": ("empty.csv", b"", "text/csv")},
    )

    assert response.status_code == 400
    assert response.json()["message"] == "O ficheiro enviado está vazio."


def test_upload_with_invalid_data_returns_422():
    response = client.post(
        "/api/v1/ingestao/clientes",
        headers=_authenticated_headers(),
        files={"arquivo": ("invalid.csv", b"wrong,columns\n1,2\n", "text/csv")},
    )

    assert response.status_code == 422
    assert "Arquivo incompatível com o contrato de ingestão." in response.json()["message"]
    assert response.json()["missing_columns"] == [
        "frequencia",
        "gasto_total",
        "id_cliente",
        "incidentes",
        "recencia_dias",
        "tier",
    ]


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
    assert response.json()["message"] == "Não foi possível processar os dados enviados. Verifique o arquivo."


def test_upload_save_failure_preserves_http_500(monkeypatch):
    def fail_to_open(*args, **kwargs):
        raise OSError("disk unavailable")

    monkeypatch.setattr("tempfile.NamedTemporaryFile", fail_to_open)
    response = client.post(
        "/api/v1/ingestao/clientes",
        headers=_authenticated_headers(),
        files={"arquivo": ("customers.csv", b"payload", "text/csv")},
    )

    assert response.status_code == 500
    assert response.json()["message"] == "Erro interno do servidor."


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
