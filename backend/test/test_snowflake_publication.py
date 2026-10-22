"""Simulated connector tests, not verification against a real Snowflake server."""

import re
from concurrent.futures import ThreadPoolExecutor
from threading import Event

import duckdb
import pandas as pd
import pytest

from app.services.datalake_service import DataLakeService
from app.services.snowflake_service import SnowflakeDataLake


class SimulatedCursor:
    def __init__(self, connection):
        self.connection = connection
        self.result = None

    def execute(self, sql, parameters=None):
        self.connection.statements.append(sql.strip())
        translated = sql.replace("CURRENT_TIMESTAMP()", "CURRENT_TIMESTAMP")
        translated = translated.replace("TO_VARCHAR(ID_CLIENTE)", "CAST(ID_CLIENTE AS VARCHAR)")
        translated = translated.replace("TIMESTAMP_TZ", "TIMESTAMPTZ")
        translated = re.sub(r"NUMBER\(\d+,\s*\d+\)", "BIGINT", translated)
        translated = translated.replace("CREATE TEMPORARY TABLE", "CREATE TABLE")
        translated = translated.replace("%s", "?")
        like = re.fullmatch(r"CREATE TABLE (\S+) LIKE (\S+)", translated)
        if like:
            translated = f"CREATE TABLE {like[1]} AS SELECT * FROM {like[2]} LIMIT 0"
        if translated.startswith("ALTER SESSION"):
            return self
        if sql.strip() == "BEGIN TRANSACTION" and self.connection.on_publish:
            self.connection.on_publish()
        self.result = self.connection.raw.execute(translated, parameters or [])
        if self.connection.fail_statement and self.connection.fail_statement(sql):
            raise RuntimeError("injected Snowflake statement failure")
        return self

    def fetch_pandas_all(self):
        return self.result.fetchdf()

    def close(self):
        pass


class SimulatedConnection:
    def __init__(self, path):
        self.raw = duckdb.connect(str(path))
        self.statements = []
        self.fail_statement = None
        self.fail_write = None
        self.on_publish = None

    def cursor(self):
        return SimulatedCursor(self)

    def close(self):
        self.raw.close()


@pytest.fixture
def snowflake(tmp_path, monkeypatch):
    path = tmp_path / "simulated-snowflake.duckdb"
    connections = []

    def connect():
        conn = SimulatedConnection(path)
        connections.append(conn)
        return conn

    def write(conn, frame, name, *, schema, auto_create_table, overwrite):
        assert not auto_create_table
        assert not overwrite
        assert "CANDIDATE_" in name
        conn.raw.execute(f"INSERT INTO {schema}.{name} SELECT * FROM frame")
        if conn.fail_write and conn.fail_write(schema):
            raise RuntimeError("injected Snowflake write failure")
        return True, 1, len(frame), None

    monkeypatch.setattr(SnowflakeDataLake, "get_connection", staticmethod(connect))
    monkeypatch.setattr("snowflake.connector.pandas_tools.write_pandas", write)
    monkeypatch.setattr(
        DataLakeService, "score_gold",
        staticmethod(lambda frame: ([0.25] * len(frame), "scored")),
    )
    raw = pd.DataFrame({
        "id_cliente": ["old"], "tier": ["DIAMANTE"], "frequencia": [4],
        "recencia_dias": [10], "gasto_total": [400.0], "incidentes": [0],
    })
    SnowflakeDataLake.process_ingestion(raw)
    return raw, connect, connections


def read_active(connect):
    conn = connect()
    try:
        return [
            SnowflakeDataLake._read_table(conn, table)
            for table in (
                "BRONZE.BRONZE_CLIENTS", "SILVER.CLEANED_CLIENTS",
                "GOLD.CLIENT_FEATURES", "GOLD.SNAPSHOT_PUBLICATION",
            )
        ]
    finally:
        conn.close()


def assert_active_unchanged(connect, previous):
    for frame, expected in zip(read_active(connect), previous, strict=True):
        pd.testing.assert_frame_equal(frame, expected)


def test_simulated_snowflake_publishes_only_dml_and_keeps_previous_visible(snowflake, monkeypatch):
    raw, connect, connections = snowflake
    previous = read_active(connect)
    writer = connect()
    writer.on_publish = lambda: assert_active_unchanged(connect, previous)
    monkeypatch.setattr(SnowflakeDataLake, "get_connection", staticmethod(lambda: writer))
    result = SnowflakeDataLake.process_ingestion(raw.assign(id_cliente="new"))
    assert result["processed_rows"] == 1
    assert read_active(connect)[2]["client_identifier"].tolist() == ["new"]
    begin = writer.statements.index("BEGIN TRANSACTION")
    publish = writer.statements[begin:]
    assert publish[-1] == "COMMIT"
    assert publish[1].startswith("UPDATE GOLD.SNAPSHOT_PUBLICATION")
    assert all(not query.startswith(("CREATE", "ALTER", "DROP")) for query in publish)
    assert sum(query.startswith("DELETE FROM") for query in publish) == 3
    assert sum(query.startswith("INSERT INTO") for query in publish) == 3
    assert not any("CREATE OR REPLACE" in query for query in writer.statements)
    candidate_names = [
        query.split()[3] for conn in connections for query in conn.statements
        if query.startswith("CREATE TEMPORARY TABLE BRONZE.")
    ]
    assert len(set(candidate_names)) == 2


@pytest.mark.parametrize("stage", [
    "bronze", "silver", "gold", "scoring", "after_scoring",
    "publish_bronze", "publish_silver", "publish_gold",
])
def test_simulated_snowflake_failure_preserves_previous_snapshot(snowflake, monkeypatch, stage):
    raw, connect, _ = snowflake
    previous = read_active(connect)
    writer = connect()
    monkeypatch.setattr(SnowflakeDataLake, "get_connection", staticmethod(lambda: writer))
    if stage in {"bronze", "after_scoring"}:
        target = "BRONZE" if stage == "bronze" else "GOLD"
        writer.fail_write = lambda schema: schema == target
    elif stage == "scoring":
        def fail_score(_frame):
            raise RuntimeError("injected scoring failure")
        monkeypatch.setattr(DataLakeService, "score_gold", fail_score)
    else:
        target = {
            "silver": "CREATE TEMPORARY TABLE SILVER.",
            "gold": "CREATE TEMPORARY TABLE GOLD.",
            "publish_bronze": "INSERT INTO BRONZE.BRONZE_CLIENTS",
            "publish_silver": "INSERT INTO SILVER.CLEANED_CLIENTS",
            "publish_gold": "INSERT INTO GOLD.CLIENT_FEATURES",
        }[stage]
        writer.fail_statement = lambda query: query.strip().startswith(target)
    candidate = raw.assign(id_cliente="failed")
    with pytest.raises(RuntimeError, match="injected"):
        SnowflakeDataLake.process_ingestion(candidate)
    assert_active_unchanged(connect, previous)
    if stage.startswith("publish_"):
        assert writer.statements[-1] == "ROLLBACK"
    else:
        assert "BEGIN TRANSACTION" not in writer.statements


def test_simulated_snowflake_rejects_partial_candidate_write(snowflake, monkeypatch):
    raw, connect, _ = snowflake
    previous = read_active(connect)
    monkeypatch.setattr(
        "snowflake.connector.pandas_tools.write_pandas",
        lambda *args, **kwargs: (True, 1, 0, None),
    )
    with pytest.raises(RuntimeError, match="todos os registros"):
        SnowflakeDataLake.process_ingestion(raw)
    assert_active_unchanged(connect, previous)


def test_simulated_concurrent_candidates_do_not_mix_snapshots(snowflake, monkeypatch):
    raw, connect, _ = snowflake
    entered, finish = Event(), Event()

    def score(frame):
        if frame["client_identifier"].tolist() == ["first"]:
            entered.set()
            assert finish.wait(5)
        return [0.25] * len(frame), "scored"

    monkeypatch.setattr(DataLakeService, "score_gold", score)
    with ThreadPoolExecutor(max_workers=1) as pool:
        first = pool.submit(SnowflakeDataLake.process_ingestion, raw.assign(id_cliente="first"))
        try:
            assert entered.wait(5)
            assert read_active(connect)[2]["client_identifier"].tolist() == ["old"]
            SnowflakeDataLake.process_ingestion(raw.assign(id_cliente="second", frequencia=9))
            assert read_active(connect)[2]["client_identifier"].tolist() == ["second"]
            assert read_active(connect)[2]["frequency"].tolist() == [9]
        finally:
            finish.set()
        first.result(timeout=5)
    published = read_active(connect)
    assert published[0]["id_cliente"].tolist() == ["first"]
    assert published[1]["client_identifier"].tolist() == ["first"]
    assert published[2]["client_identifier"].tolist() == ["first"]
    assert published[2]["frequency"].tolist() == [4]
