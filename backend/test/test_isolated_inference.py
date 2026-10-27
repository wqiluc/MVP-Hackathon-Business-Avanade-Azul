import json
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from app.services.ml.churn_service import ChurnService
from app.services.ml.clv_service import ClvService
from app.services.ml.inference_provider import (
    LocalMLflowInferenceProvider,
    ModelInferenceError,
)
from app.services.ml.model_contracts import CHURN_FEATURES

REPO_ROOT = Path(__file__).resolve().parents[2]
CLV_MODEL_DIR = REPO_ROOT / "pacote_CLV" / "modelo_clv"
CHURN_MODEL_DIR = REPO_ROOT / "modelo_churn"
CLV_PYTHON = REPO_ROOT / "backend" / ".venv-clv" / "bin" / "python"


def _features():
    return {
        feature: (
            "app" if feature == "canal_aquisicao"
            else "pessoa_fisica" if feature == "tipo_cliente"
            else 1
        )
        for feature in CHURN_FEATURES
    }


def _model_dir(tmp_path):
    model_dir = tmp_path / "modelo_clv"
    model_dir.mkdir()
    (model_dir / "registered_model_meta").write_text(
        "model_name: workspace.default.clv_gb\nmodel_version: '3'\n",
        encoding="utf-8",
    )
    python = tmp_path / "python"
    python.write_text("", encoding="utf-8")
    return model_dir, python


def test_isolated_provider_sends_contract_frame_and_reads_worker_output(
    tmp_path, monkeypatch
):
    model_dir, python = _model_dir(tmp_path)
    calls = []

    def fake_run(command, **kwargs):
        calls.append((command, json.loads(kwargs["input"]), kwargs["timeout"]))
        return subprocess.CompletedProcess(
            command, 0, stdout=json.dumps({"predictions": [12.5], "classes": None})
        )

    monkeypatch.setattr(subprocess, "run", fake_run)
    loader_calls = []
    provider = LocalMLflowInferenceProvider(
        {"clv": str(model_dir)},
        model_loader=loader_calls.append,
        python_executables={"clv": str(python)},
        timeout_seconds=7,
    )
    frame = pd.DataFrame([_features()])[list(CHURN_FEATURES)]

    result = provider.predict("clv", frame, "predict")

    assert result.predictions == [12.5]
    assert result.classes is None
    assert result.model_name == "workspace.default.clv_gb"
    assert result.model_version == "3"
    assert result.source == "local"
    assert loader_calls == []
    command, payload, timeout = calls[0]
    assert command[0] == str(python)
    assert command[1].endswith("isolated_model_worker.py")
    assert payload["model_path"] == str(model_dir.resolve())
    assert payload["method"] == "predict"
    assert payload["frame"]["columns"] == list(CHURN_FEATURES)
    assert timeout == 7


def test_isolated_provider_only_applies_to_configured_model(tmp_path, monkeypatch):
    model_dir, python = _model_dir(tmp_path)
    monkeypatch.setattr(
        subprocess, "run", lambda *a, **k: pytest.fail("subprocess must not run")
    )

    class Model:
        classes_ = np.array([0, 1])

        def predict_proba(self, frame):
            return np.array([[0.4, 0.6]] * len(frame))

    provider = LocalMLflowInferenceProvider(
        {"churn": str(model_dir)},
        model_loader=lambda path: Model(),
        python_executables={"clv": str(python), "churn": ""},
    )

    result = provider.predict("churn", pd.DataFrame([_features()]), "predict_proba")

    assert result.classes == (0, 1)


@pytest.mark.parametrize(
    "completed",
    [
        subprocess.CompletedProcess([], 1, stdout="", stderr="boom"),
        subprocess.CompletedProcess([], 0, stdout="not json"),
        subprocess.CompletedProcess([], 0, stdout=json.dumps({"other": 1})),
    ],
)
def test_isolated_worker_failures_become_model_inference_error(
    tmp_path, monkeypatch, completed
):
    model_dir, python = _model_dir(tmp_path)
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: completed)
    provider = LocalMLflowInferenceProvider(
        {"clv": str(model_dir)}, python_executables={"clv": str(python)}
    )

    with pytest.raises(ModelInferenceError):
        provider.predict("clv", pd.DataFrame([_features()]), "predict")


def test_isolated_worker_timeout_becomes_model_inference_error(tmp_path, monkeypatch):
    model_dir, python = _model_dir(tmp_path)

    def timeout(command, **kwargs):
        raise subprocess.TimeoutExpired(command, kwargs["timeout"])

    monkeypatch.setattr(subprocess, "run", timeout)
    provider = LocalMLflowInferenceProvider(
        {"clv": str(model_dir)}, python_executables={"clv": str(python)}
    )

    with pytest.raises(ModelInferenceError, match="timed out"):
        provider.predict("clv", pd.DataFrame([_features()]), "predict")


def test_missing_isolated_interpreter_is_reported(tmp_path):
    model_dir, _ = _model_dir(tmp_path)
    provider = LocalMLflowInferenceProvider(
        {"clv": str(model_dir)},
        python_executables={"clv": str(tmp_path / "missing-python")},
    )

    with pytest.raises(ModelInferenceError, match="ML_CLV_PYTHON"):
        provider.predict("clv", pd.DataFrame([_features()]), "predict")


@pytest.mark.skipif(
    not (CLV_PYTHON.is_file() and CLV_MODEL_DIR.is_dir() and CHURN_MODEL_DIR.is_dir()),
    reason="Real CLV/churn artifacts or backend/.venv-clv are not available locally.",
)
def test_real_clv_v3_runs_isolated_while_churn_runs_in_process():
    provider = LocalMLflowInferenceProvider(
        {"churn": str(CHURN_MODEL_DIR), "clv": str(CLV_MODEL_DIR)},
        python_executables={"clv": str(CLV_PYTHON)},
    )
    rows = [_features(), {**_features(), "gasto_total_12m": 50000}]

    clv = ClvService(provider).predict_many(rows)
    churn = ChurnService(provider).predict_many(rows)

    assert [p.model_name for p in clv] == ["workspace.default.clv_gb"] * 2
    assert {p.model_version for p in clv} == {"3"}
    assert all(np.isfinite(p.value) for p in clv)
    assert {p.model_name for p in churn} == {"workspace.default.churn_gb2"}
    assert {p.model_version for p in churn} == {"1"}
    assert all(0 <= p.score <= 1 for p in churn)
