import math
from collections.abc import Mapping
from numbers import Integral, Real
from typing import Any

from app.services.ml.model_contracts import (
    CHURN_FEATURES,
    CLV_INTEGER_FEATURES,
    STRING_FEATURES,
    ChurnFeatures,
    ClvFeatures,
)


class MissingModelFeaturesError(ValueError):
    def __init__(self, missing: list[str]):
        self.missing = tuple(missing)
        super().__init__("Missing required model features: " + ", ".join(missing))


class InvalidModelFeaturesError(ValueError):
    pass


class FeatureBuilder:
    """Select and validate only explicitly supplied model features; no aliases/defaults."""

    @staticmethod
    def _build(source: Mapping[str, Any], integer_features: frozenset[str]):
        missing = [feature for feature in CHURN_FEATURES if feature not in source]
        if missing:
            raise MissingModelFeaturesError(missing)

        values: dict[str, Any] = {}
        for feature in CHURN_FEATURES:
            value = source[feature]
            if value is None:
                raise InvalidModelFeaturesError(f"Feature {feature!r} cannot be null.")

            if feature in STRING_FEATURES:
                if not isinstance(value, str):
                    raise InvalidModelFeaturesError(
                        f"Feature {feature!r} must be a string."
                    )
                values[feature] = value
                continue

            if isinstance(value, bool) or not isinstance(value, Real):
                raise InvalidModelFeaturesError(
                    f"Feature {feature!r} must be numeric."
                )
            if feature in integer_features:
                if isinstance(value, Integral):
                    values[feature] = int(value)
                    continue
                numeric = float(value)
                if not math.isfinite(numeric) or not numeric.is_integer():
                    raise InvalidModelFeaturesError(
                        f"Feature {feature!r} must be an integer."
                    )
                values[feature] = int(numeric)
                continue
            numeric = float(value)
            if not math.isfinite(numeric):
                raise InvalidModelFeaturesError(
                    f"Feature {feature!r} must be finite."
                )
            values[feature] = numeric
        return values

    @classmethod
    def build_churn(cls, source: Mapping[str, Any]):
        return ChurnFeatures.model_validate(cls._build(source, frozenset()))

    @classmethod
    def build_clv(cls, source: Mapping[str, Any]):
        return ClvFeatures.model_validate(
            cls._build(source, CLV_INTEGER_FEATURES)
        )

    @classmethod
    def build_frame(cls, rows, model: str):
        """Build one validated mapping per row of a pandas-like frame."""
        if model not in {"churn", "clv"}:
            raise ValueError("Model must be 'churn' or 'clv'.")
        builder = cls.build_churn if model == "churn" else cls.build_clv
        return [builder(row).model_dump() for row in rows.to_dict(orient="records")]
