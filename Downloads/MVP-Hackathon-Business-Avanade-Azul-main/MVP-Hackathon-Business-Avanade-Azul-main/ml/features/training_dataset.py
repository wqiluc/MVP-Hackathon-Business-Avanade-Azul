import pandas as pd


FEATURE_COLUMNS = [
    "frequency",
    "recency_days",
    "total_spend",
    "flight_incidents",
    "avg_ticket",
]


def prepare_training_dataset(gold: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
    features = gold[FEATURE_COLUMNS].fillna(0)
    target = gold["high_risk_flag"]
    return features, target
