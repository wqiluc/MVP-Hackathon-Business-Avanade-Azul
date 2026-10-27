from collections.abc import Iterable
from enum import Enum

import pandas as pd

from app.services.ml.model_contracts import CHURN_FEATURES, STRING_FEATURES


class IngestionContract(str, Enum):
    CRM_CANONICAL = "CRM_CANONICAL"
    ML_FEATURES_52 = "ML_FEATURES_52"
    UNKNOWN = "UNKNOWN"


CRM_CANONICAL_COLUMNS = (
    "id_cliente",
    "tier",
    "recencia_dias",
    "frequencia",
    "gasto_total",
    "incidentes",
)

# Single source of truth: the model contract. Targets (churn_180d, clv_12m) and
# identifiers/PII (cliente_id, cpf, ...) are deliberately not part of it.
ML_FEATURE_COLUMNS = CHURN_FEATURES

ACCEPTED_CONTRACTS_MESSAGE = (
    "Arquivo incompatível com o contrato de ingestão. "
    "Contratos aceitos: CRM_CANONICAL e ML_FEATURES_52. "
    f"Contrato CRM: {', '.join(CRM_CANONICAL_COLUMNS)}. "
    f"Contrato ML: as {len(ML_FEATURE_COLUMNS)} features do modelo de Churn."
)


def detect_ingestion_contract(columns: Iterable[object]) -> IngestionContract:
    """Deterministic, name-exact detection; ML has priority over CRM."""
    names = {str(column).strip().lower() for column in columns}
    if set(ML_FEATURE_COLUMNS).issubset(names):
        return IngestionContract.ML_FEATURES_52
    if set(CRM_CANONICAL_COLUMNS).issubset(names):
        return IngestionContract.CRM_CANONICAL
    return IngestionContract.UNKNOWN


def extract_ml_features(frame: pd.DataFrame) -> pd.DataFrame:
    """Keep only the contract features, in contract order; targets and PII are dropped here."""
    lowered = frame.rename(columns=lambda column: str(column).strip().lower())
    selected = lowered.loc[:, list(ML_FEATURE_COLUMNS)].copy()
    invalid: list[str] = []
    for feature in ML_FEATURE_COLUMNS:
        if feature in STRING_FEATURES:
            continue
        converted = pd.to_numeric(selected[feature].replace("", pd.NA), errors="coerce")
        if converted.isna().any():
            invalid.append(feature)
        selected[feature] = converted
    if invalid:
        raise ValueError(f"Invalid or missing values in model features: {', '.join(invalid)}")
    return selected
