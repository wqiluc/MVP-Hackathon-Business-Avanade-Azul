import csv
import json
from pathlib import Path

import pandas as pd
import pytest

from ai.llm.contracts import recommendation_profile
from app.services.ml.feature_builder import FeatureBuilder
from app.services.ml.ingestion_contracts import (
    CRM_CANONICAL_COLUMNS,
    IngestionContract,
    detect_ingestion_contract,
)
from app.services.ml.model_contracts import CHURN_FEATURES, STRING_FEATURES
from data.ingestion.file_reader import FileContractError, FileReader

REAL_CSV = Path.home() / "Downloads" / "clientes_churn_limpo (1).csv"


def _ml_row(**extra):
    row = {f: ("x" if f in STRING_FEATURES else 1) for f in CHURN_FEATURES}
    row.update(extra)
    return row


def test_detects_crm_canonical():
    assert detect_ingestion_contract(CRM_CANONICAL_COLUMNS) is IngestionContract.CRM_CANONICAL


def test_detects_ml_features_52():
    assert len(CHURN_FEATURES) == 52
    assert detect_ingestion_contract(list(CHURN_FEATURES)) is IngestionContract.ML_FEATURES_52


def test_target_column_does_not_change_ml_contract():
    columns = [*CHURN_FEATURES, "churn_180d", "clv_12m", "cpf"]
    assert detect_ingestion_contract(columns) is IngestionContract.ML_FEATURES_52


def test_ml_has_priority_over_crm():
    columns = [*CHURN_FEATURES, *CRM_CANONICAL_COLUMNS]
    assert detect_ingestion_contract(columns) is IngestionContract.ML_FEATURES_52


def test_incomplete_ml_contract_is_unknown():
    assert detect_ingestion_contract(list(CHURN_FEATURES)[:-1]) is IngestionContract.UNKNOWN


def test_similar_names_are_not_accepted_as_ml():
    columns = [f"{f}_x" for f in CHURN_FEATURES]
    assert detect_ingestion_contract(columns) is IngestionContract.UNKNOWN
    assert detect_ingestion_contract(["frequencia", "gasto_total"]) is IngestionContract.UNKNOWN


def test_unknown_upload_message_lists_accepted_contracts(tmp_path):
    path = tmp_path / "x.csv"
    path.write_text("wrong,columns\n1,2\n")
    with pytest.raises(FileContractError) as exc:
        FileReader.read_file(str(path), "csv")
    assert exc.value.ingestion_contract == "UNKNOWN"
    message = str(exc.value)
    assert "CRM_CANONICAL" in message and "ML_FEATURES_52" in message
    assert "id_cliente" in message and "52 features" in message


def test_crm_upload_is_tagged_with_contract(tmp_path):
    path = tmp_path / "crm.csv"
    pd.DataFrame(
        {"id_cliente": ["1"], "tier": ["Diamante"], "frequencia": [1],
         "recencia_dias": [1], "gasto_total": [1.0], "incidentes": [0]}
    ).to_csv(path, index=False)
    assert FileReader.read_file(str(path), "csv").attrs["ingestion_contract"] == "CRM_CANONICAL"


def test_ml_upload_is_accepted_and_reduced_to_contract_features(tmp_path):
    path = tmp_path / "ml.csv"
    pd.DataFrame([_ml_row(churn_180d=0, cpf="000", clv_12m=1.0)]).to_csv(path, index=False)
    frame = FileReader.read_file(str(path), "csv")
    assert frame.attrs["ingestion_contract"] == "ML_FEATURES_52"
    assert list(frame.columns) == list(CHURN_FEATURES)


def test_ml_upload_with_invalid_values_is_rejected(tmp_path):
    path = tmp_path / "ml.csv"
    row = _ml_row()
    numeric = next(f for f in CHURN_FEATURES if f not in STRING_FEATURES)
    row[numeric] = "abc"
    pd.DataFrame([row]).to_csv(path, index=False)
    with pytest.raises(FileContractError):
        FileReader.read_file(str(path), "csv")


def test_ml_scoring_sends_only_52_features_and_never_the_target(tmp_path, monkeypatch):
    from unittest.mock import MagicMock
    from app.services import datalake_service as ds
    from app.services.ml.model_contracts import ChurnPrediction, ClvPrediction

    path = tmp_path / "ml.csv"
    pd.DataFrame([_ml_row(churn_180d=1, score_churn=1, churn_probabilidade=1,
                          is_churn=1, clv_12m=5, cpf="1", data_nascimento="x")]).to_csv(path, index=False)
    frame = FileReader.read_file(str(path), "csv")
    sent = {}
    meta = dict(model_name="m", model_version="1", source="local", timestamp=pd.Timestamp.now(tz="UTC"))

    def churn(features):
        sent["churn"] = features
        return [ChurnPrediction(score=0.3, **meta) for _ in features]

    def clv(features):
        sent["clv"] = features
        return [ClvPrediction(value=10.0, **meta) for _ in features]

    monkeypatch.setattr("app.services.ml.churn_service.ChurnService",
                        lambda: MagicMock(predict_many=churn))
    monkeypatch.setattr("app.services.ml.clv_service.ClvService",
                        lambda: MagicMock(predict_many=clv))
    summary = ds.DataLakeService.score_ml_features(frame)
    for model in ("churn", "clv"):
        assert set(sent[model][0]) == set(CHURN_FEATURES)
    assert summary["status"] == "scored_not_persisted"
    assert "id_cliente" not in str(summary)


def test_crm_canonical_minimal_dataset_does_not_require_52_features(tmp_path):
    path = tmp_path / "crm.csv"
    pd.DataFrame({"id_cliente": ["1"], "tier": ["Diamante"], "frequencia": [1],
                  "recencia_dias": [1], "gasto_total": [1.0], "incidentes": [0]}).to_csv(path, index=False)
    assert FileReader.read_file(str(path), "csv").attrs["ingestion_contract"] == "CRM_CANONICAL"


def test_garbage_and_lookalike_headers_are_unknown(tmp_path):
    for header in ("foo,bar,baz", "frequencia_fake,gasto_total_fake,incidentes_fake"):
        path = tmp_path / "x.csv"
        path.write_text(f"{header}\n1,2,3\n")
        with pytest.raises(FileContractError) as exc:
            FileReader.read_file(str(path), "csv")
        assert exc.value.ingestion_contract == "UNKNOWN"
        assert "CRM_CANONICAL" in str(exc.value) and "ML_FEATURES_52" in str(exc.value)


def test_training_columns_are_not_required_for_inference(tmp_path):
    for column in ("churn_180d", "score_churn", "churn_probabilidade", "is_churn", "clv_12m", "cpf"):
        assert column not in CHURN_FEATURES


def test_target_and_pii_never_reach_model_features():
    source = _ml_row(churn_180d=1, clv_12m=9.0, cpf="000", cliente_id="c1")
    churn = FeatureBuilder.build_churn(source).model_dump()
    assert list(churn) == list(CHURN_FEATURES)
    for forbidden in ("churn_180d", "clv_12m", "cpf", "cliente_id"):
        assert forbidden not in churn


def test_builder_does_not_alias_crm_fields_to_model_features():
    from app.services.ml.feature_builder import MissingModelFeaturesError

    crm = {"frequencia": 1, "gasto_total": 1.0, "incidentes": 0, "recencia_dias": 1}
    with pytest.raises(MissingModelFeaturesError):
        FeatureBuilder.build_churn(crm)


def test_pii_is_not_in_llm_profile():
    state = {
        "tier": "Safira", "frequency": 1, "total_spend": 1.0, "churn_score": 0.5,
        "flight_incidents": 0, "incident_type": None, "value_at_risk": 1.0,
        "graph_rag_context": {}, "cpf": "123.456.789-00", "email": "a@b.com",
        "nome": "Fulano", "telefone": "11999999999", "client_identifier": "abc",
    }
    payload = json.dumps(recommendation_profile(state))
    for value in ("123.456.789-00", "a@b.com", "Fulano", "11999999999", "abc"):
        assert value not in payload


@pytest.mark.skipif(not REAL_CSV.exists(), reason="local real CSV not available")
def test_real_local_csv_header_is_ml_features_52():
    with REAL_CSV.open(newline="") as handle:
        header = next(csv.reader(handle))
    assert detect_ingestion_contract(header) is IngestionContract.ML_FEATURES_52
