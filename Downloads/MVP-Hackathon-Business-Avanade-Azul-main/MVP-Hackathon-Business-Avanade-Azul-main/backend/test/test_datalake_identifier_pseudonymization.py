import pandas as pd

from app.config import settings
from app.core.security import anonymize_identifier
from app.services.datalake_service import DataLakeService, DuckDBDataLake


def test_ingestion_pseudonymizes_source_ids_before_selected_backend(monkeypatch):
    source = pd.DataFrame(
        {
            "id_cliente": ["customer-123", "customer-456", "customer-123", None],
            "tier": ["OURO", "PRATA", "OURO", "PRATA"],
        }
    )
    source_before = source.copy(deep=True)
    received = []
    monkeypatch.setattr(DataLakeService, "_ler_arquivo", lambda *_: source)
    monkeypatch.setattr(settings, "DATA_LAKE_BACKEND", "duckdb")
    monkeypatch.setattr(
        DuckDBDataLake,
        "process_ingestion",
        lambda dataframe: received.append(dataframe.copy()) or {"status": "success"},
    )

    result = DataLakeService.process_ingestion("clients.csv", "csv")

    assert result == {"status": "success"}
    assert len(received) == 1
    persisted_input = received[0]
    assert (
        persisted_input["id_cliente"]
        .dropna()
        .str.fullmatch(r"AZ-[0-9a-f]{32}")
        .all()
    )
    assert persisted_input.loc[0, "id_cliente"] == persisted_input.loc[2, "id_cliente"]
    assert persisted_input.loc[0, "id_cliente"] != persisted_input.loc[1, "id_cliente"]
    assert pd.isna(persisted_input.loc[3, "id_cliente"])
    source_ids = set(source["id_cliente"].dropna())
    persisted_ids = set(persisted_input["id_cliente"].dropna())
    assert source_ids.isdisjoint(persisted_ids)
    pd.testing.assert_frame_equal(source, source_before)


def test_client_identifier_is_stable_for_the_same_signing_secret(monkeypatch):
    clients = pd.DataFrame({"id_cliente": ["customer-123"]})
    monkeypatch.setattr(settings, "JWT_SECRET_KEY", "stable-test-secret")

    first = DataLakeService._replace_source_ids_with_internal_ids(clients)
    second = DataLakeService._replace_source_ids_with_internal_ids(clients)

    assert first.loc[0, "id_cliente"] == second.loc[0, "id_cliente"]
    assert first.loc[0, "id_cliente"] == anonymize_identifier("customer-123")
    assert clients.loc[0, "id_cliente"] == "customer-123"
