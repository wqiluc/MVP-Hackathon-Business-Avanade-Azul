from concurrent.futures import ThreadPoolExecutor
from threading import Event

import pandas as pd
import pytest

from app.config import settings
from app.services.crm_service import CrmService
from app.services.datalake_service import DataLakeService, DuckDBDataLake
from data.storage.duckdb_adapter import DuckDBAdapter


def dataset(identifier="candidate", rows=2):
    return pd.DataFrame({
        "id_cliente": [f"{identifier}-{i}" for i in range(rows)],
        "tier": ["DIAMANTE"] * rows,
        "frequencia": [4] * rows,
        "recencia_dias": [10] * rows,
        "gasto_total": [400.0] * rows,
        "incidentes": [0] * rows,
    })


@pytest.fixture
def lake(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "DATA_LAKE_BACKEND", "duckdb")
    monkeypatch.setattr(settings, "DUCKDB_PATH", str(tmp_path / "snapshots.duckdb"))
    monkeypatch.setattr(
        DataLakeService, "score_gold",
        staticmethod(lambda frame: ([0.25] * len(frame), "scored")),
    )
    DataLakeService.init_schema()
    DuckDBDataLake.process_ingestion(dataset("previous", 1))
    return tmp_path


def read_layers():
    conn = DataLakeService.get_connection()
    try:
        return [
            conn.execute(f"SELECT * FROM {table}").fetchdf()
            for table in (
                "bronze.raw_clients", "silver.cleaned_clients",
                "gold.client_features", "gold.snapshot_publication",
            )
        ]
    finally:
        conn.close()


def assert_unchanged(expected):
    for actual, previous in zip(read_layers(), expected, strict=True):
        pd.testing.assert_frame_equal(actual, previous)


def test_successful_snapshot_replaces_all_layers_together(lake):
    previous = read_layers()
    DuckDBDataLake.process_ingestion(dataset())
    current = read_layers()
    assert [len(frame) for frame in current[:3]] == [2, 2, 2]
    assert current[2]["churn_score"].tolist() == [0.25, 0.25]
    assert current[3]["execution_id"].iloc[0] != previous[3]["execution_id"].iloc[0]
    assert len(CrmService.listar()) == 2


@pytest.mark.parametrize("stage", ["bronze", "silver", "gold", "scoring", "after_scoring"])
def test_stage_failure_keeps_every_previous_layer(lake, monkeypatch, stage):
    from data.bronze.duckdb_writer import DuckDBBronzeWriter
    from data.silver.duckdb_transformer import DuckDBSilverTransformer
    from data.gold.duckdb_transformer import DuckDBGoldTransformer

    previous = read_layers()
    owner, method = {
        "bronze": (DuckDBBronzeWriter, "write_raw_clients"),
        "silver": (DuckDBSilverTransformer, "transform_cleaned_clients"),
        "gold": (DuckDBGoldTransformer, "transform_client_features"),
        "scoring": (DataLakeService, "score_gold"),
        "after_scoring": (DuckDBAdapter, "write_gold"),
    }[stage]
    original = getattr(owner, method)

    def fail(*args):
        if stage != "scoring":
            original(*args)
        raise RuntimeError("injected stage failure")

    monkeypatch.setattr(owner, method, fail)
    with pytest.raises(RuntimeError, match="injected"):
        DuckDBDataLake.process_ingestion(dataset())
    assert_unchanged(previous)
    assert len(CrmService.listar()) == 1


def test_readers_see_previous_snapshot_and_second_writer_is_rejected(lake, monkeypatch):
    from app.services.snapshot import SnapshotBusyError

    entered, finish = Event(), Event()
    original = DataLakeService.score_gold
    previous = read_layers()

    def paused_score(frame):
        entered.set()
        assert finish.wait(5), "writer release timed out"
        return original(frame)

    monkeypatch.setattr(DataLakeService, "score_gold", paused_score)
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(DuckDBDataLake.process_ingestion, dataset())
        try:
            assert entered.wait(5)
            assert_unchanged(previous)
            assert len(CrmService.listar()) == 1
            with pytest.raises(SnapshotBusyError):
                DuckDBDataLake.process_ingestion(dataset("other", 3))
        finally:
            finish.set()
        future.result(timeout=5)
    assert len(CrmService.listar()) == 2


def test_invalid_scores_cannot_replace_previous_snapshot(lake, monkeypatch):
    previous = read_layers()
    monkeypatch.setattr(
        DataLakeService, "score_gold",
        lambda frame: ([float("nan")] * len(frame), "scored"),
    )
    with pytest.raises(RuntimeError, match="scores"):
        DuckDBDataLake.process_ingestion(dataset())
    assert_unchanged(previous)


def test_unregistered_model_publishes_explicit_null_scores(lake, monkeypatch):
    monkeypatch.setattr(
        DataLakeService, "score_gold",
        lambda frame: ([float("nan")] * len(frame), "awaiting_model_registration"),
    )
    result = DuckDBDataLake.process_ingestion(dataset())
    assert result["scoring_status"] == "awaiting_model_registration"
    assert DataLakeService.read_gold()["churn_score"].isna().all()


def test_candidate_cannot_change_client_attributes_during_scoring(lake, monkeypatch):
    previous = read_layers()

    def mutate(frame):
        frame["frequency"] = 999
        return [0.25] * len(frame), "scored"

    monkeypatch.setattr(DataLakeService, "score_gold", mutate)
    with pytest.raises(RuntimeError, match="atributos"):
        DuckDBDataLake.process_ingestion(dataset())
    assert_unchanged(previous)


def test_first_upload_failure_leaves_no_partially_created_tables(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "DUCKDB_PATH", str(tmp_path / "first.duckdb"))

    def fail(_frame):
        raise RuntimeError("scoring unavailable")

    monkeypatch.setattr(DataLakeService, "score_gold", fail)
    with pytest.raises(RuntimeError):
        DuckDBDataLake.process_ingestion(dataset())
    conn = DataLakeService.get_connection()
    try:
        assert conn.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema IN ('bronze','silver','gold')"
        ).fetchall() == []
    finally:
        conn.close()


def test_api_stays_responsive_during_upload_and_returns_safe_conflict(lake, monkeypatch, caplog):
    from fastapi.testclient import TestClient
    from run import app

    monkeypatch.setattr(settings, "ENVIRONMENT", "development")
    monkeypatch.setattr(settings, "DEMO_EMAIL", "snapshot@example.invalid")
    monkeypatch.setattr(settings, "DEMO_PASSWORD", "fixture-password")
    api = TestClient(app)
    token = api.post("/api/v1/auth/login", json={
        "email": settings.DEMO_EMAIL, "senha": settings.DEMO_PASSWORD,
    }).json()["token"]
    headers = {"Authorization": f"Bearer {token}"}
    entered, finish = Event(), Event()
    original = DataLakeService.score_gold

    def paused_score(frame):
        entered.set()
        assert finish.wait(5)
        return original(frame)

    monkeypatch.setattr(DataLakeService, "score_gold", paused_score)

    def upload():
        return api.post(
            "/api/v1/ingestao/clientes", headers=headers,
            files={"arquivo": ("clients.csv", dataset().to_csv(index=False).encode(), "text/csv")},
        )

    with caplog.at_level("INFO", logger="app.services.snapshot"):
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(upload)
            try:
                assert entered.wait(5)
                listing = api.get("/api/v1/clientes", headers=headers)
                assert listing.status_code == 200 and len(listing.json()) == 1
                assert api.get("/api/v1/health/live").status_code == 200
                assert upload().status_code == 409
            finally:
                finish.set()
            assert future.result(timeout=5).status_code == 200
    published = [record for record in caplog.records if "snapshot published" in record.message]
    assert len(published) == 1
    run_id = published[0].message.split("execution_id=")[1].split()[0]
    lifecycle = [record.message for record in caplog.records if run_id in record.message]
    assert any("ingestion started" in message for message in lifecycle)
    assert any("ingestion succeeded" in message and "duration_seconds=" in message for message in lifecycle)
    assert "fixture-password" not in caplog.text and token not in caplog.text
