import ast
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest
import requests

from app.services.inference_service import predict_churn
from ml.inference.churn_predictor import ChurnPredictor


def _feature_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "frequency": [10, 20],
            "recency_days": [30, 60],
            "total_spend": [1000.0, 2000.0],
            "flight_incidents": [1, 0],
            "avg_ticket": [100.0, 100.0],
        }
    )


def test_empty_dataframe_returns_empty_list():
    assert ChurnPredictor.predict(pd.DataFrame(), "") == []


def test_without_serving_url_uses_current_rules_and_rounding():
    df = pd.DataFrame(
        {
            "frequency": [0, 24, None, 0],
            "recency_days": [0, 0, None, 1],
            "flight_incidents": [0, 0, None, 0],
        }
    )

    assert ChurnPredictor.predict(df, "", allow_local_inference=True) == [
        0.08,
        0.01,
        0.08,
        0.082,
    ]


def test_rules_keep_current_upper_bound_and_null_handling():
    df = pd.DataFrame(
        {
            "frequency": [0, None],
            "recency_days": [180, None],
            "flight_incidents": [3, None],
        }
    )

    scores = ChurnPredictor.predict(df, "", allow_local_inference=True)

    assert scores == [0.89, 0.08]
    assert all(0.01 <= score <= 0.99 for score in scores)


def test_serving_post_uses_expected_endpoint_timeout_and_feature_payload():
    df = _feature_frame()
    df.loc[0, "avg_ticket"] = np.nan
    with patch("ml.inference.churn_predictor.requests.post") as post:
        post.return_value.json.return_value = {"predictions": [0.2, 0.8]}
        scores = ChurnPredictor.predict(df, "https://serving.example/invocations")

    assert scores == [0.2, 0.8]
    post.assert_called_once_with(
        "https://serving.example/invocations",
        json={
            "dataframe_split": {
                "index": [0, 1],
                "columns": [
                    "frequency",
                    "recency_days",
                    "total_spend",
                    "flight_incidents",
                    "avg_ticket",
                ],
                "data": [
                    [10.0, 30.0, 1000.0, 1.0, 0.0],
                    [20.0, 60.0, 2000.0, 0.0, 100.0],
                ],
            }
        },
        timeout=15,
    )


def test_serving_accepts_direct_list_response_and_uses_last_prediction_value():
    df = _feature_frame()
    with patch("ml.inference.churn_predictor.requests.post") as post:
        post.return_value.json.return_value = [[0.1, 0.2], [0.8, 0.9]]
        assert ChurnPredictor.predict(df, "https://serving.example/invocations") == [0.2, 0.9]


def test_serving_scales_values_above_one_and_clips_and_rounds():
    df = _feature_frame()
    with patch("ml.inference.churn_predictor.requests.post") as post:
        post.return_value.json.return_value = {"predictions": [123.4567, -5.0]}
        scores = ChurnPredictor.predict(df, "https://serving.example/invocations")

    assert scores == [0.123, 0.0]


def test_serving_clips_values_to_zero_and_one_and_rounds_to_three_decimals():
    df = _feature_frame()
    with patch("ml.inference.churn_predictor.requests.post") as post:
        post.return_value.json.return_value = {"predictions": [-0.23456, 0.93456]}
        scores = ChurnPredictor.predict(df, "https://serving.example/invocations")

    assert scores == [0.0, 0.935]


def test_http_failure_propagates_when_serving_is_configured():
    df = _feature_frame()

    with patch(
        "ml.inference.churn_predictor.requests.post",
        side_effect=requests.Timeout("serving unavailable"),
    ):
        with pytest.raises(RuntimeError, match="Falha ao consultar MLflow Serving"):
            ChurnPredictor.predict(df, "https://serving.example/invocations")


def test_missing_serving_url_requires_explicit_local_mode():
    with pytest.raises(RuntimeError, match="MLflow Serving não está configurado"):
        ChurnPredictor.predict(_feature_frame(), "")


def test_legacy_facade_delegates_with_configured_serving_url(monkeypatch):
    df = _feature_frame()
    monkeypatch.setattr("app.services.inference_service.settings.MLFLOW_SERVING_URL", "https://serving.example")

    with patch(
        "app.services.inference_service.ChurnPredictor.predict",
        return_value=[0.1, 0.2],
    ) as predict:
        assert predict_churn(df) == [0.1, 0.2]

    predict.assert_called_once_with(
        df,
        "https://serving.example",
        allow_local_inference=False,
    )


def test_churn_predictor_module_does_not_import_application_modules():
    source_path = Path(__file__).parents[2] / "ml" / "inference" / "churn_predictor.py"
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    imported_modules = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_modules.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.append(node.module)

    assert not any(
        module == "app" or module.startswith("app.") or module == "fastapi" or module.startswith("fastapi.")
        for module in imported_modules
    )
