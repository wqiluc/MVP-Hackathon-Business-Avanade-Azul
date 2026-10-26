import logging
from datetime import datetime, timezone
from time import monotonic

import numpy as np
import pandas as pd

from app.services.ml.feature_builder import FeatureBuilder
from app.services.ml.inference_provider import (
    ModelInferenceError,
    ModelInferenceProvider,
    get_inference_provider,
)
from app.services.ml.model_contracts import ChurnPrediction

logger = logging.getLogger(__name__)


class ChurnService:
    def __init__(self, provider: ModelInferenceProvider | None = None):
        self.provider = provider or get_inference_provider()

    def predict(self, features: dict) -> ChurnPrediction:
        return self.predict_many([features])[0]

    def predict_many(self, features: list[dict]) -> list[ChurnPrediction]:
        if not features:
            return []
        validated = [FeatureBuilder.build_churn(row) for row in features]
        frame = pd.DataFrame([row.model_dump() for row in validated])
        started = monotonic()
        try:
            result = self.provider.predict("churn", frame, "predict_proba")
            probabilities = np.asarray(result.predictions, dtype=float)
            if probabilities.shape != (len(features), len(result.classes or ())):
                raise ModelInferenceError(
                    "Churn model output must contain one probability per class and input row."
                )
            if result.classes is None or len(set(result.classes)) != len(result.classes):
                raise ModelInferenceError(
                    "Churn model class labels are unavailable or invalid."
                )
            if 1 not in result.classes:
                raise ModelInferenceError(
                    "Churn model does not expose the verified positive class label 1."
                )
            if (
                not np.isfinite(probabilities).all()
                or (probabilities < 0).any()
                or (probabilities > 1).any()
            ):
                raise ModelInferenceError("Churn model returned invalid probabilities.")
            timestamp = datetime.now(timezone.utc)
            predictions = [
                ChurnPrediction(
                    score=float(row[result.classes.index(1)]),
                    model_name=result.model_name,
                    model_version=result.model_version,
                    source=result.source,
                    timestamp=timestamp,
                )
                for row in probabilities
            ]
            logger.info(
                "ML inference completed model=churn model_name=%s model_version=%s "
                "provider=%s duration_seconds=%.3f",
                result.model_name,
                result.model_version,
                result.source,
                monotonic() - started,
            )
            return predictions
        except Exception as error:
            logger.warning(
                "ML inference failed model=churn provider=%s error_type=%s "
                "duration_seconds=%.3f",
                self.provider.source,
                type(error).__name__,
                monotonic() - started,
            )
            raise
