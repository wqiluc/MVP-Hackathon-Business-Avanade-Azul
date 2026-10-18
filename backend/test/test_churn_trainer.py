from unittest.mock import patch

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier as SklearnRandomForestClassifier
from sklearn.model_selection import train_test_split as sklearn_train_test_split

from ml.training import churn_trainer


def test_trainer_preserves_split_parameters_model_parameters_and_predictions():
    features = pd.DataFrame(
        {
            "frequency": range(10),
            "recency_days": [index * 2 for index in range(10)],
        }
    )
    target = pd.Series([index % 2 for index in range(10)], name="high_risk_flag")
    split_arguments = {}
    model_arguments = {}

    class RecordingRandomForestClassifier(SklearnRandomForestClassifier):
        def __init__(self, **kwargs):
            model_arguments.update(kwargs)
            super().__init__(**kwargs)

    def record_split(x, y, **kwargs):
        split_arguments["x"] = x.copy()
        split_arguments["y"] = y.copy()
        split_arguments["kwargs"] = kwargs.copy()
        return sklearn_train_test_split(x, y, **kwargs)

    with (
        patch.object(churn_trainer, "train_test_split", side_effect=record_split) as split,
        patch.object(churn_trainer, "RandomForestClassifier", RecordingRandomForestClassifier),
    ):
        model, y_test, predictions = churn_trainer.train_churn_classifier(features, target)

    pd.testing.assert_frame_equal(split_arguments["x"], features)
    pd.testing.assert_series_equal(split_arguments["y"], target)
    assert split_arguments["kwargs"] == {"test_size": 0.2, "random_state": 42}
    split.assert_called_once()
    assert model_arguments == {"n_estimators": 100, "max_depth": 8, "random_state": 42}
    assert isinstance(model, SklearnRandomForestClassifier)
    assert len(y_test) == 2
    assert isinstance(predictions, np.ndarray)
    assert len(predictions) == len(y_test)
