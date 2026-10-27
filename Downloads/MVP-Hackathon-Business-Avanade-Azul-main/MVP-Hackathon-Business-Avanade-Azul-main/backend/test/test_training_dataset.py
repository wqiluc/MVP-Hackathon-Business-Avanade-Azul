import pandas as pd

from ml.features.training_dataset import FEATURE_COLUMNS, prepare_training_dataset


def test_training_dataset_selects_only_features_in_training_order():
    gold = pd.DataFrame(
        {
            "high_risk_flag": [0, 1],
            "avg_ticket": [25.0, 50.0],
            "unused_column": ["ignored", "ignored"],
            "flight_incidents": [0, 2],
            "total_spend": [100.0, 200.0],
            "recency_days": [10, 30],
            "frequency": [4, 8],
        }
    )

    features, target = prepare_training_dataset(gold)

    assert list(features.columns) == [
        "frequency",
        "recency_days",
        "total_spend",
        "flight_incidents",
        "avg_ticket",
    ]
    assert FEATURE_COLUMNS == list(features.columns)
    assert "unused_column" not in features.columns
    assert isinstance(features, pd.DataFrame)
    assert isinstance(target, pd.Series)


def test_training_dataset_fills_feature_nulls_and_preserves_target():
    gold = pd.DataFrame(
        {
            "frequency": [None, 2],
            "recency_days": [10, None],
            "total_spend": [None, 200.0],
            "flight_incidents": [0, None],
            "avg_ticket": [25.0, None],
            "high_risk_flag": [1, 0],
        }
    )

    features, target = prepare_training_dataset(gold)

    assert features.to_dict(orient="records") == [
        {
            "frequency": 0.0,
            "recency_days": 10.0,
            "total_spend": 0.0,
            "flight_incidents": 0.0,
            "avg_ticket": 25.0,
        },
        {
            "frequency": 2.0,
            "recency_days": 0.0,
            "total_spend": 200.0,
            "flight_incidents": 0.0,
            "avg_ticket": 0.0,
        },
    ]
    pd.testing.assert_series_equal(target, gold["high_risk_flag"])
