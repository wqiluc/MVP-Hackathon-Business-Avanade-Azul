from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import numpy as np
import pandas as pd
import pytest
import requests

from app.services.ml.churn_service import ChurnService
from app.services.ml.clv_service import ClvService
from app.services.ml.feature_builder import (
    FeatureBuilder,
    InvalidModelFeaturesError,
    MissingModelFeaturesError,
)
from app.services.ml.inference_provider import (
    DatabricksServingInferenceProvider,
    LocalMLflowInferenceProvider,
    ModelInferenceError,
)
from app.services.ml.model_contracts import (
    CHURN_FEATURES,
    CLV_INTEGER_FEATURES,
)


def _features():
    return {
        feature: (
            "app" if feature == "canal_aquisicao"
            else "pessoa_fisica" if feature == "tipo_cliente"
            else 1
        )
        for feature in CHURN_FEATURES
    }


class FakeProvider:
    source = "local"

    def __init__(self, predictions, classes=(0, 1), model_name="test-model"):
        self.predictions = predictions
        self.classes = classes
        self.model_name = model_name
        self.calls = []

    def predict(self, model_key, frame, method):
        self.calls.append((model_key, frame.copy(), method))
        return SimpleNamespace(
            predictions=self.predictions,
            classes=self.classes,
            model_name=self.model_name,
            model_version="test-version",
            source=self.source,
        )


def test_model_contracts_have_exactly_the_artifact_feature_names():
    churn = FeatureBuilder.build_churn(_features())
    clv = FeatureBuilder.build_clv(_features())

    assert len(CHURN_FEATURES) == 52
    assert tuple(churn.model_dump()) == CHURN_FEATURES
    assert tuple(clv.model_dump()) == CHURN_FEATURES
    assert all(isinstance(churn.model_dump()[key], float) for key in CHURN_FEATURES if key not in {"canal_aquisicao", "tipo_cliente"})
    assert all(isinstance(clv.model_dump()[key], int) for key in CLV_INTEGER_FEATURES)


def test_feature_builder_rejects_missing_features_without_filling_them():
    features = _features()
    del features["gasto_total_12m"]

    with pytest.raises(MissingModelFeaturesError) as error:
        FeatureBuilder.build_churn(features)

    assert error.value.missing == ("gasto_total_12m",)


@pytest.mark.parametrize(
    ("feature", "value"),
    [
        ("dias_desde_ultimo_voo", "18"),
        ("canal_aquisicao", 5),
        ("gasto_total_12m", float("nan")),
        ("voos_12m", True),
    ],
)
def test_feature_builder_rejects_invalid_types_and_nonfinite_values(feature, value):
    features = _features()
    features[feature] = value

    with pytest.raises(InvalidModelFeaturesError):
        FeatureBuilder.build_churn(features)


def test_feature_builder_produces_only_the_model_contract():
    source = _features() | {"client_identifier": "AZ-pseudonym"}

    built = FeatureBuilder.build_churn(source)

    assert tuple(built.model_dump()) == CHURN_FEATURES
    assert "client_identifier" not in built.model_dump()


def test_churn_service_maps_probability_using_the_matching_class_label():
    provider = FakeProvider([[0.81, 0.19]], classes=(1, 0))

    prediction = ChurnService(provider).predict(_features())

    assert prediction.score == pytest.approx(0.81)
    assert prediction.model_name == "test-model"
    assert prediction.model_version == "test-version"
    assert prediction.source == "local"
    assert provider.calls[0][0] == "churn"
    assert provider.calls[0][2] == "predict_proba"
    assert tuple(provider.calls[0][1].columns) == CHURN_FEATURES


@pytest.mark.parametrize(
    ("probabilities", "classes"),
    [
        ([[0.3]], (0, 1)),
        ([[0.3, 0.7]], (0, 0)),
        ([[0.3, 0.7]], (0, 2)),
        ([[float("nan"), 0.7]], (0, 1)),
    ],
)
def test_churn_service_rejects_unknown_classes_or_invalid_probability_output(
    probabilities, classes
):
    provider = FakeProvider(probabilities, classes=classes)
    with pytest.raises(ModelInferenceError):
        ChurnService(provider).predict(_features())


def test_churn_service_batches_rows_without_changing_output_order():
    provider = FakeProvider([[0.9, 0.1], [0.2, 0.8]])
    service = ChurnService(provider)

    predictions = service.predict_many([_features(), _features()])

    assert [prediction.score for prediction in predictions] == [0.1, 0.8]
    assert len(provider.calls) == 1
    assert len(provider.calls[0][1]) == 2


def test_clv_service_returns_scalar_predictions_and_metadata():
    provider = FakeProvider([1500.25], model_name="clv-test")

    prediction = ClvService(provider).predict(_features())

    assert prediction.value == pytest.approx(1500.25)
    assert prediction.model_name == "clv-test"
    assert prediction.source == "local"
    assert provider.calls[0][0] == "clv"
    assert provider.calls[0][2] == "predict"
    assert all(
        isinstance(provider.calls[0][1].iloc[0][feature], (int, np.integer))
        for feature in CLV_INTEGER_FEATURES
    )


def test_clv_integer_features_preserve_values_beyond_float_precision():
    features = _features()
    features["saldo_pontos"] = 2**60 + 1

    built = FeatureBuilder.build_clv(features)

    assert built.saldo_pontos == 2**60 + 1


@pytest.mark.parametrize("output", [[1.0, 2.0], [float("inf")], ["invalid"]])
def test_clv_service_rejects_invalid_model_output(output):
    with pytest.raises((ModelInferenceError, ValueError)):
        ClvService(FakeProvider(output)).predict(_features())


def test_local_provider_loads_model_lazily_and_reads_registered_metadata(
    tmp_path, monkeypatch
):
    model_path = tmp_path / "model"
    model_path.mkdir()
    (model_path / "registered_model_meta").write_text(
        "model_name: example.model\nmodel_version: '4'\n", encoding="utf-8"
    )
    model = SimpleNamespace(
        classes_=np.array([0, 1]),
        predict_proba=Mock(return_value=np.array([[0.4, 0.6]])),
    )
    load_model = Mock(return_value=model)
    provider = LocalMLflowInferenceProvider(
        {"churn": str(model_path)}, model_loader=load_model
    )

    assert load_model.call_count == 0
    result = provider.predict("churn", pd.DataFrame([_features()]), "predict_proba")

    load_model.assert_called_once_with(str(model_path.resolve()))
    assert result.model_name == "example.model"
    assert result.model_version == "4"
    assert result.classes == (0, 1)


def test_databricks_provider_uses_mocked_http_and_model_serving_contract(monkeypatch):
    post = Mock()
    post.return_value.json.return_value = {"predictions": [[0.25, 0.75]]}
    monkeypatch.setattr("app.services.ml.inference_provider.requests.post", post)
    provider = DatabricksServingInferenceProvider(
        "https://workspace.example",
        "not-a-real-token",
        {"churn": "churn-serving"},
        4,
        {"churn": (0, 1)},
    )

    result = provider.predict("churn", pd.DataFrame([_features()]), "predict_proba")

    assert result.predictions == [[0.25, 0.75]]
    assert result.classes == (0, 1)
    assert result.source == "databricks"
    assert result.model_name == "churn-serving"
    assert post.call_args.kwargs["timeout"] == 4
    assert post.call_args.kwargs["headers"] == {
        "Authorization": "Bearer not-a-real-token"
    }
    assert "client_identifier" not in post.call_args.kwargs["json"]["dataframe_split"]["columns"]


def test_databricks_timeout_is_reported_without_credentials(monkeypatch):
    monkeypatch.setattr(
        "app.services.ml.inference_provider.requests.post",
        Mock(side_effect=requests.Timeout("private endpoint detail")),
    )
    provider = DatabricksServingInferenceProvider(
        "https://workspace.example", "sensitive", {"clv": "clv-serving"}, 1
    )

    with pytest.raises(ModelInferenceError, match="timed out") as error:
        provider.predict("clv", pd.DataFrame([_features()]), "predict")
    assert "sensitive" not in str(error.value)
    assert "private endpoint detail" not in str(error.value)


@pytest.mark.parametrize(
    ("response", "exception"),
    [
        (SimpleNamespace(raise_for_status=Mock(side_effect=requests.HTTPError("secret")), json=Mock()), "request failed"),
        (SimpleNamespace(raise_for_status=Mock(), json=Mock(side_effect=ValueError("bad json"))), "invalid JSON"),
        (SimpleNamespace(raise_for_status=Mock(), json=Mock(return_value=[])), "predictions field"),
    ],
)
def test_databricks_provider_rejects_http_and_invalid_responses(
    monkeypatch, response, exception
):
    monkeypatch.setattr(
        "app.services.ml.inference_provider.requests.post", Mock(return_value=response)
    )
    provider = DatabricksServingInferenceProvider(
        "https://workspace.example", "sensitive", {"clv": "clv-serving"}, 1
    )

    with pytest.raises(ModelInferenceError, match=exception):
        provider.predict("clv", pd.DataFrame([_features()]), "predict")


def test_real_model_services_do_not_load_artifacts_during_import():
    source = Path(__file__).parents[1] / "app" / "services" / "ml" / "inference_provider.py"
    text = source.read_text(encoding="utf-8")

    assert "mlflow.sklearn.load_model(cache_key)" in text
    assert text.index("def _load") < text.index("mlflow.sklearn.load_model(cache_key)")
