import pytest

from ml.evaluation.metrics import calculate_classification_metrics


def test_calculate_classification_metrics_returns_accuracy_precision_and_recall():
    metrics = calculate_classification_metrics(
        y_test=[0, 0, 1, 1],
        y_pred=[0, 1, 1, 1],
    )

    assert metrics == {
        "accuracy": pytest.approx(0.75),
        "precision": pytest.approx(2 / 3),
        "recall": pytest.approx(1.0),
    }


def test_precision_without_positive_predictions_uses_zero_division_zero():
    metrics = calculate_classification_metrics(
        y_test=[0, 1],
        y_pred=[0, 0],
    )

    assert metrics == {"accuracy": 0.5, "precision": 0.0, "recall": 0.0}
