from sklearn.metrics import accuracy_score, precision_score, recall_score


def calculate_classification_metrics(y_test, y_pred) -> dict[str, float]:
    return {
        "accuracy": float(accuracy_score(y_test, y_pred)),
        "precision": float(precision_score(y_test, y_pred, zero_division=0)),
        "recall": float(recall_score(y_test, y_pred, zero_division=0)),
    }
