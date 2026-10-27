import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split


CHURN_MODEL_PARAMETERS = {"n_estimators": 100, "max_depth": 8, "random_state": 42}


def train_churn_classifier(
    features: pd.DataFrame,
    target: pd.Series,
) -> tuple[RandomForestClassifier, pd.Series, np.ndarray]:
    x_train, x_test, y_train, y_test = train_test_split(
        features,
        target,
        test_size=0.2,
        random_state=42,
    )
    model = RandomForestClassifier(**CHURN_MODEL_PARAMETERS)
    model.fit(x_train, y_train)
    predictions = model.predict(x_test)
    return model, y_test, predictions
