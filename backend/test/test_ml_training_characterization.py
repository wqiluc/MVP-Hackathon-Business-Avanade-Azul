from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest
from sklearn.ensemble import RandomForestClassifier as SklearnRandomForestClassifier
from sklearn.metrics import accuracy_score, recall_score
from sklearn.metrics import precision_score as sklearn_precision_score
from sklearn.model_selection import train_test_split as sklearn_train_test_split

from app.services import ml_service
from ml.training import churn_trainer


FEATURES = ["frequency", "recency_days", "total_spend", "flight_incidents", "avg_ticket"]


def _training_frame(row_count: int = 10) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "client_identifier": [f"AZ-{index}" for index in range(row_count)],
            "frequency": [index + 1 for index in range(row_count)],
            "recency_days": [index * 7 for index in range(row_count)],
            "total_spend": [None if index == 2 else 1000.0 * (index + 1) for index in range(row_count)],
            "flight_incidents": [index % 3 for index in range(row_count)],
            "avg_ticket": [None if index == 4 else 100.0 + index for index in range(row_count)],
            "high_risk_flag": [index % 2 for index in range(row_count)],
            "unused_column": ["ignored"] * row_count,
        }
    )


def _mock_mlflow():
    run = SimpleNamespace(info=SimpleNamespace(run_id="characterization-run-id"))
    run_context = MagicMock()
    run_context.__enter__.return_value = run
    return {
        "configure": patch("ml.models.mlflow_tracker.mlflow.set_tracking_uri"),
        "set_experiment": patch("ml.models.mlflow_tracker.mlflow.set_experiment"),
        "start_run": patch("ml.models.mlflow_tracker.mlflow.start_run", return_value=run_context),
        "log_params": patch("ml.models.mlflow_tracker.mlflow.log_params"),
        "log_metric": patch("ml.models.mlflow_tracker.mlflow.log_metric"),
        "log_model": patch(
            "ml.models.mlflow_tracker.mlflow.sklearn.log_model",
            return_value=SimpleNamespace(model_uri="runs:/characterization-run-id/churn_rf_model"),
        ),
        "register": patch(
            "app.services.ml_service.register_churn_model",
            return_value=SimpleNamespace(
                model_name="AeroShieldChurnModel",
                model_version="4",
                alias="champion",
                run_id="characterization-run-id",
            ),
        ),
    }


def test_training_rejects_empty_gold_with_current_value_error():
    mlflow_mocks = _mock_mlflow()
    with (
        mlflow_mocks["set_experiment"] as set_experiment,
        patch("app.services.ml_service.DataLakeService.read_gold", return_value=pd.DataFrame()),
    ):
        with pytest.raises(
            ValueError,
            match="^A camada Ouro do Data Lake está vazia\\. Execute o upload de dados "
            "\\(/data/ingest\\) antes de treinar o modelo\\.$",
        ):
            ml_service.train_and_register_churn_model()

    set_experiment.assert_called_once_with("Azul_CRM_Churn_Prediction")


def test_training_rejects_gold_with_fewer_than_five_records():
    mlflow_mocks = _mock_mlflow()
    with (
        mlflow_mocks["set_experiment"],
        patch(
            "app.services.ml_service.DataLakeService.read_gold",
            return_value=_training_frame(4),
        ),
    ):
        with pytest.raises(
            ValueError,
            match="^Quantidade insuficiente de registros na camada Ouro para treinar o modelo "
            "\\(mínimo de 5 registros\\)\\.$",
        ):
            ml_service.train_and_register_churn_model()


def test_valid_training_preserves_features_split_model_metrics_and_mlflow_contract():
    gold = _training_frame()
    split_arguments = {}
    estimator_calls = {}

    class RecordingRandomForestClassifier(SklearnRandomForestClassifier):
        def __init__(self, **kwargs):
            estimator_calls["constructions"] = estimator_calls.get("constructions", 0) + 1
            estimator_calls["parameters"] = kwargs.copy()
            super().__init__(**kwargs)

        def fit(self, x_train, y_train, *args, **kwargs):
            estimator_calls["x_train"] = x_train.copy()
            estimator_calls["y_train"] = y_train.copy()
            return super().fit(x_train, y_train, *args, **kwargs)

        def predict(self, x_test, *args, **kwargs):
            estimator_calls["x_test"] = x_test.copy()
            predictions = super().predict(x_test, *args, **kwargs)
            estimator_calls["predictions"] = predictions.copy()
            return predictions

    def record_split(x, y, **kwargs):
        split_arguments["x"] = x.copy()
        split_arguments["y"] = y.copy()
        split_arguments["kwargs"] = kwargs.copy()
        split = sklearn_train_test_split(x, y, **kwargs)
        split_arguments["result"] = split
        return split

    mlflow_mocks = _mock_mlflow()
    with (
        mlflow_mocks["configure"] as configure,
        mlflow_mocks["set_experiment"] as set_experiment,
        mlflow_mocks["start_run"] as start_run,
        mlflow_mocks["log_params"] as log_params,
        mlflow_mocks["log_metric"] as log_metric,
        mlflow_mocks["log_model"] as log_model,
        mlflow_mocks["register"] as register_model,
        patch("app.services.ml_service.DataLakeService.read_gold", return_value=gold),
        patch.object(churn_trainer, "train_test_split", side_effect=record_split) as split,
        patch.object(churn_trainer, "RandomForestClassifier", RecordingRandomForestClassifier),
        patch(
            "ml.evaluation.metrics.precision_score",
            wraps=sklearn_precision_score,
        ) as precision,
    ):
        result = ml_service.train_and_register_churn_model()

    expected_x = gold[FEATURES].fillna(0)
    expected_y = gold["high_risk_flag"]
    pd.testing.assert_frame_equal(split_arguments["x"], expected_x)
    pd.testing.assert_series_equal(split_arguments["y"], expected_y)
    assert list(split_arguments["x"].columns) == FEATURES
    assert split_arguments["kwargs"] == {"test_size": 0.2, "random_state": 42}
    split.assert_called_once()

    expected_parameters = {"n_estimators": 100, "max_depth": 8, "random_state": 42}
    assert estimator_calls["parameters"] == expected_parameters
    pd.testing.assert_frame_equal(estimator_calls["x_train"], split_arguments["x"].loc[estimator_calls["x_train"].index])
    pd.testing.assert_series_equal(estimator_calls["y_train"], split_arguments["y"].loc[estimator_calls["y_train"].index])
    pd.testing.assert_frame_equal(estimator_calls["x_test"], split_arguments["x"].loc[estimator_calls["x_test"].index])
    assert estimator_calls["constructions"] == 1
    _, _, _, y_test = split_arguments["result"]
    precision.assert_called_once()
    precision_y, precision_predictions = precision.call_args.args
    pd.testing.assert_series_equal(precision_y, y_test)
    np.testing.assert_array_equal(precision_predictions, estimator_calls["predictions"])
    assert precision.call_args.kwargs == {"zero_division": 0}

    expected_metrics = {
        "accuracy": round(float(accuracy_score(y_test, estimator_calls["predictions"])), 4),
        "precision": round(
            float(sklearn_precision_score(y_test, estimator_calls["predictions"], zero_division=0)),
            4,
        ),
        "recall": round(
            float(recall_score(y_test, estimator_calls["predictions"], zero_division=0)),
            4,
        ),
    }
    set_experiment.assert_called_once_with("Azul_CRM_Churn_Prediction")
    start_run.assert_called_once_with()
    configure.assert_called_once()
    log_params.assert_called_once_with(expected_parameters)
    log_metric.assert_any_call("accuracy", accuracy_score(y_test, estimator_calls["predictions"]))
    log_metric.assert_any_call(
        "precision",
        sklearn_precision_score(y_test, estimator_calls["predictions"], zero_division=0),
    )
    log_metric.assert_any_call(
        "recall",
        recall_score(y_test, estimator_calls["predictions"], zero_division=0),
    )
    assert log_metric.call_count == 3
    log_model.assert_called_once()
    assert isinstance(log_model.call_args.args[0], SklearnRandomForestClassifier)
    assert log_model.call_args.kwargs["name"] == "churn_rf_model"
    register_model.assert_called_once_with(
        "runs:/characterization-run-id/churn_rf_model",
        "characterization-run-id",
    )
    assert result == {
        "run_id": "characterization-run-id",
        **expected_metrics,
        "status": "Modelo AeroShieldChurnModel v4 registrado como champion no MLflow",
    }
    assert all(isinstance(result[metric], float) for metric in ("accuracy", "precision", "recall"))
    assert all(round(result[metric], 4) == result[metric] for metric in ("accuracy", "precision", "recall"))


def test_training_propagates_gold_read_error_without_swallowing_it():
    mlflow_mocks = _mock_mlflow()
    with (
        mlflow_mocks["set_experiment"],
        patch(
            "app.services.ml_service.DataLakeService.read_gold",
            side_effect=RuntimeError("gold unavailable"),
        ),
    ):
        with pytest.raises(RuntimeError, match="^gold unavailable$"):
            ml_service.train_and_register_churn_model()
