from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from mlflow.exceptions import MlflowException
from mlflow.protos import databricks_pb2

from ml.models.mlflow_tracker import (
    EXPERIMENT_NAME,
    MODEL_ALIAS,
    MODEL_ARTIFACT_PATH,
    MODEL_NAME,
    SKOPS_TRUSTED_TYPES,
    ActiveChurnModel,
    MLflowChurnRun,
    configure_tracking,
    get_active_churn_model,
    register_churn_model,
    start_churn_run,
)


def test_configure_tracking_sets_tracking_and_registry_uris():
    with (
        patch("ml.models.mlflow_tracker.mlflow.set_tracking_uri") as set_tracking_uri,
        patch("ml.models.mlflow_tracker.mlflow.set_registry_uri") as set_registry_uri,
    ):
        configure_tracking("http://mlflow.example")

    set_tracking_uri.assert_called_once_with("http://mlflow.example")
    set_registry_uri.assert_called_once_with("http://mlflow.example")


def test_configure_tracking_rejects_an_empty_uri():
    with pytest.raises(ValueError, match="MLFLOW_TRACKING_URI deve estar configurado"):
        configure_tracking("")


def test_training_logs_parameters_metrics_and_sklearn_model_with_narrow_skops_trust():
    underlying_run = SimpleNamespace(info=SimpleNamespace(run_id="run-id"))
    run_context = MagicMock()
    run_context.__enter__.return_value = underlying_run
    model_info = SimpleNamespace(model_uri="runs:/run-id/churn_rf_model")
    params = {"n_estimators": 100, "max_depth": 8, "random_state": 42}
    metrics = {"accuracy": 0.9, "precision": 0.8, "recall": 0.7}
    model = object()

    with (
        patch("ml.models.mlflow_tracker.mlflow.log_params") as log_params,
        patch("ml.models.mlflow_tracker.mlflow.log_metric") as log_metric,
        patch(
            "ml.models.mlflow_tracker.mlflow.sklearn.log_model",
            return_value=model_info,
        ) as log_model,
    ):
        model_uri = MLflowChurnRun.log_training(model, params, metrics)

    assert model_uri == "runs:/run-id/churn_rf_model"
    log_params.assert_called_once_with(params)
    assert log_metric.call_args_list == [
        (("accuracy", 0.9), {}),
        (("precision", 0.8), {}),
        (("recall", 0.7), {}),
    ]
    log_model.assert_called_once_with(
        model,
        name=MODEL_ARTIFACT_PATH,
        pyfunc_predict_fn="predict_proba",
        skops_trusted_types=SKOPS_TRUSTED_TYPES,
    )


def test_model_registration_sets_and_verifies_the_active_alias():
    version = SimpleNamespace(
        name=MODEL_NAME,
        version="3",
        status="READY",
        run_id="run-id",
    )
    client = MagicMock()
    client.get_model_version_by_alias.return_value = version
    with (
        patch("ml.models.mlflow_tracker.mlflow.register_model", return_value=version) as register,
        patch("ml.models.mlflow_tracker._client", return_value=client),
    ):
        result = register_churn_model("runs:/run-id/churn_rf_model", "run-id")

    register.assert_called_once_with(
        "runs:/run-id/churn_rf_model",
        MODEL_NAME,
        await_registration_for=300,
    )
    client.set_registered_model_alias.assert_called_once_with(
        MODEL_NAME,
        MODEL_ALIAS,
        "3",
    )
    client.get_model_version_by_alias.assert_called_once_with(MODEL_NAME, MODEL_ALIAS)
    assert result.model_name == MODEL_NAME
    assert result.model_version == "3"
    assert result.alias == MODEL_ALIAS
    assert result.run_id == "run-id"


def test_model_registration_does_not_promote_a_version_that_is_not_ready():
    version = SimpleNamespace(
        name=MODEL_NAME,
        version="3",
        status="FAILED_REGISTRATION",
        run_id="run-id",
    )
    with (
        patch("ml.models.mlflow_tracker.mlflow.register_model", return_value=version),
        patch("ml.models.mlflow_tracker._client") as client,
        pytest.raises(RuntimeError, match="não deixou a versão 3 pronta"),
    ):
        register_churn_model("runs:/run-id/churn_rf_model", "run-id")

    client.assert_not_called()


def test_active_model_reads_version_alias_and_metrics_from_registry_and_run():
    version = SimpleNamespace(
        name=MODEL_NAME,
        version="3",
        status="READY",
        run_id="run-id",
    )
    run = SimpleNamespace(
        data=SimpleNamespace(metrics={"accuracy": 0.9, "precision": 0.8}),
        info=SimpleNamespace(start_time=123456),
    )
    client = MagicMock()
    client.get_model_version_by_alias.return_value = version
    client.get_run.return_value = run
    with patch("ml.models.mlflow_tracker._client", return_value=client):
        result = get_active_churn_model()

    assert result == ActiveChurnModel(
        model_name=MODEL_NAME,
        model_version="3",
        alias=MODEL_ALIAS,
        run_id="run-id",
        status="READY",
        metrics={"accuracy": 0.9, "precision": 0.8},
        start_time=123456,
    )
    client.get_model_version_by_alias.assert_called_once_with(MODEL_NAME, MODEL_ALIAS)
    client.get_run.assert_called_once_with("run-id")


def test_active_model_is_none_when_registry_has_no_model_alias():
    client = MagicMock()
    client.get_model_version_by_alias.side_effect = MlflowException(
        "Model alias does not exist",
        error_code=databricks_pb2.RESOURCE_DOES_NOT_EXIST,
    )
    with patch("ml.models.mlflow_tracker._client", return_value=client):
        assert get_active_churn_model() is None


def test_tracking_run_exposes_the_actual_run_id():
    underlying_run = SimpleNamespace(info=SimpleNamespace(run_id="run-id"))
    run_context = MagicMock()
    run_context.__enter__.return_value = underlying_run
    with patch(
        "ml.models.mlflow_tracker.mlflow.start_run",
        return_value=run_context,
    ) as start_run:
        with start_churn_run() as run:
            assert isinstance(run, MLflowChurnRun)
            assert run.run_id == "run-id"

    start_run.assert_called_once_with()
