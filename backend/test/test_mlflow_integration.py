import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import mlflow
import pandas as pd
import pytest
import requests
from mlflow.tracking import MlflowClient
from fastapi.testclient import TestClient

from app.config import settings
from app.core.security import get_current_user
from app.services.datalake_service import DataLakeService
from app.services.inference_service import predict_churn
from run import app as fastapi_app
from data.storage.duckdb_adapter import DuckDBAdapter
from ml.models.mlflow_tracker import EXPERIMENT_NAME, MODEL_ALIAS, MODEL_NAME


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def _available_port() -> int:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return listener.getsockname()[1]


def _wait_for_server(url: str, process: subprocess.Popen, log_path: Path) -> None:
    deadline = time.monotonic() + 90
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise AssertionError(
                f"MLflow process exited with {process.returncode}:\n"
                f"{log_path.read_text(encoding='utf-8', errors='replace')}"
            )
        try:
            response = requests.get(url, timeout=1)
            if response.ok:
                return
        except requests.RequestException:
            pass
        time.sleep(0.25)
    raise AssertionError(
        f"MLflow endpoint did not become ready at {url}:\n"
        f"{log_path.read_text(encoding='utf-8', errors='replace')}"
    )


def _stop_process(process: subprocess.Popen | None) -> None:
    if process is None or process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=10)


def test_mlflow_tracking_registry_serving_and_application_scoring(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    if os.getenv("MLFLOW_INTEGRATION_TESTS") != "1":
        pytest.skip("Set MLFLOW_INTEGRATION_TESTS=1 to run real MLflow services.")

    tracking_port = _available_port()
    serving_port = _available_port()
    tracking_uri = f"http://127.0.0.1:{tracking_port}"
    database_path = tmp_path / "tracking.db"
    artifact_path = tmp_path / "artifacts"
    artifact_path.mkdir()
    server_log_path = tmp_path / "tracking-server.log"
    serving_log_path = tmp_path / "serving-server.log"
    environment = os.environ.copy()
    environment.update(
        {
            "MLFLOW_TRACKING_URI": tracking_uri,
            "MLFLOW_REGISTRY_URI": tracking_uri,
            "MLFLOW_DISABLE_AGENT_HINT": "1",
            "PATH": (
                f"{Path(sys.executable).parent}{os.pathsep}"
                f"{environment.get('PATH', '')}"
            ),
        }
    )

    with server_log_path.open("w", encoding="utf-8") as server_log:
        tracking_process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "mlflow",
                "server",
                "--backend-store-uri",
                f"sqlite:///{database_path}",
                "--artifacts-destination",
                artifact_path.as_uri(),
                "--host",
                "127.0.0.1",
                "--port",
                str(tracking_port),
                "--workers",
                "1",
            ],
            cwd=REPOSITORY_ROOT,
            env=environment,
            stdout=server_log,
            stderr=subprocess.STDOUT,
        )

    serving_process = None
    try:
        _wait_for_server(f"{tracking_uri}/health", tracking_process, server_log_path)
        monkeypatch.setattr(settings, "MLFLOW_TRACKING_URI", tracking_uri)
        monkeypatch.setattr(settings, "MLFLOW_SERVING_URL", "")
        monkeypatch.setattr(settings, "MLFLOW_LOCAL_INFERENCE", False)
        monkeypatch.setattr(settings, "DUCKDB_PATH", str(tmp_path / "application.duckdb"))
        monkeypatch.setattr(settings, "DATA_LAKE_BACKEND", "duckdb")

        monkeypatch.setitem(
            fastapi_app.dependency_overrides,
            get_current_user,
            lambda: {"sub": "mlflow-integration-test"},
        )
        DataLakeService.init_schema()
        connection = DataLakeService.get_connection()
        rows = 60
        gold = pd.DataFrame(
            {
                "frequency": [index % 24 for index in range(rows)],
                "recency_days": [index * 3 for index in range(rows)],
                "total_spend": [500.0 + index * 75 for index in range(rows)],
                "flight_incidents": [index % 4 for index in range(rows)],
                "avg_ticket": [60.0 + index * 8 for index in range(rows)],
                "high_risk_flag": [int(index % 3 == 0) for index in range(rows)],
            }
        )
        DuckDBAdapter.write_gold(connection, gold)
        connection.close()

        with TestClient(fastapi_app) as api_client:
            no_active_model = api_client.get("/api/v1/modelo")
            assert no_active_model.status_code == 200
            assert no_active_model.json()["status"] == "aguardando-registro"

            training_response = api_client.post("/api/v1/modelo/train")
            assert training_response.status_code == 200
            training_result = training_response.json()

        assert training_result["run_id"]
        assert "registrado como champion" in training_result["status"]

        client = MlflowClient(tracking_uri=tracking_uri, registry_uri=tracking_uri)
        experiment = client.get_experiment_by_name(EXPERIMENT_NAME)
        assert experiment is not None
        runs = client.search_runs([experiment.experiment_id], max_results=1)
        assert len(runs) == 1
        assert runs[0].info.run_id == training_result["run_id"]
        assert runs[0].data.params["n_estimators"] == "100"
        assert set(runs[0].data.metrics) >= {"accuracy", "precision", "recall"}

        active_version = client.get_model_version_by_alias(MODEL_NAME, MODEL_ALIAS)
        assert active_version.status == "READY"
        assert active_version.run_id == training_result["run_id"]
        assert training_result["status"].startswith(
            f"Modelo {MODEL_NAME} v{active_version.version}"
        )
        with TestClient(fastapi_app) as api_client:
            active_model_response = api_client.get("/api/v1/modelo")
        assert active_model_response.status_code == 200
        assert active_model_response.json()["versao"] == active_version.version

        with serving_log_path.open("w", encoding="utf-8") as serving_log:
            serving_process = subprocess.Popen(
                [
                    sys.executable,
                    "-m",
                    "mlflow",
                    "models",
                    "serve",
                    "--model-uri",
                    f"models:/{MODEL_NAME}@{MODEL_ALIAS}",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    str(serving_port),
                    "--env-manager",
                    "local",
                ],
                cwd=REPOSITORY_ROOT,
                env=environment,
                stdout=serving_log,
                stderr=subprocess.STDOUT,
            )

        serving_base_url = f"http://127.0.0.1:{serving_port}"
        _wait_for_server(f"{serving_base_url}/ping", serving_process, serving_log_path)
        serving_url = f"{serving_base_url}/invocations"
        monkeypatch.setattr(settings, "MLFLOW_SERVING_URL", serving_url)

        connection = DataLakeService.get_connection()
        expected_scores = predict_churn(gold.drop(columns=["high_risk_flag"]))
        DataLakeService._score_gold(connection)
        scored_gold = DuckDBAdapter.read_gold(connection)
        connection.close()

        assert "churn_score" in scored_gold.columns
        assert scored_gold["churn_score"].tolist() == expected_scores
        assert all(0 <= score <= 1 for score in expected_scores)

        mlflow.set_tracking_uri(tracking_uri)
        served_model = mlflow.pyfunc.load_model(
            f"models:/{MODEL_NAME}@{MODEL_ALIAS}"
        )
        direct_model_scores = served_model.predict(
            gold.drop(columns=["high_risk_flag"]).iloc[:5]
        )[:, -1]
        assert expected_scores[:5] == pytest.approx(direct_model_scores.tolist(), abs=0.001)
    finally:
        _stop_process(serving_process)
        _stop_process(tracking_process)
