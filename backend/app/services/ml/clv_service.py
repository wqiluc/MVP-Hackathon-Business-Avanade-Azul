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
from app.services.ml.model_contracts import ClvPrediction

logger = logging.getLogger(__name__)


class ClvService:
    def __init__(self, provider: ModelInferenceProvider | None = None):
        self.provider = provider or get_inference_provider()

    def predict(self, features: dict) -> ClvPrediction:
        return self.predict_many([features])[0]

    def predict_many(self, features: list[dict]) -> list[ClvPrediction]:
        if not features:
            return []
        validated = [FeatureBuilder.build_clv(row) for row in features]
        frame = pd.DataFrame([row.model_dump() for row in validated])
        started = monotonic()
        try:
            result = self.provider.predict("clv", frame, "predict")
            values = np.asarray(result.predictions, dtype=float)
            if values.size != len(features) or not np.isfinite(values).all():
                raise ModelInferenceError(
                    "CLV model must return one finite numeric value per input row."
                )
            timestamp = datetime.now(timezone.utc)
            predictions = [
                ClvPrediction(
                    value=float(value),
                    model_name=result.model_name,
                    model_version=result.model_version,
                    source=result.source,
                    timestamp=timestamp,
                )
                for value in values.reshape(-1)
            ]
            logger.info(
                "ML inference completed model=clv model_name=%s model_version=%s "
                "provider=%s duration_seconds=%.3f",
                result.model_name,
                result.model_version,
                result.source,
                monotonic() - started,
            )
            return predictions
        except Exception as error:
            logger.warning(
                "ML inference failed model=clv provider=%s error_type=%s "
                "duration_seconds=%.3f",
                self.provider.source,
                type(error).__name__,
                monotonic() - started,
            )
            raise
