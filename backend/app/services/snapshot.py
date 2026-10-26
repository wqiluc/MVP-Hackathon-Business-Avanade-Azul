import logging
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path
from threading import Lock
from time import monotonic
from uuid import uuid4

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)
_execution_id: ContextVar[str | None] = ContextVar("ingestion_execution_id", default=None)
_locks_guard = Lock()
_writer_locks: dict[str, Lock] = {}


class SnapshotBusyError(RuntimeError):
    pass


def execution_id() -> str:
    return _execution_id.get() or uuid4().hex


@contextmanager
def ingestion_run(backend: str):
    if _execution_id.get() is not None:
        yield
        return
    run_id = uuid4().hex
    token = _execution_id.set(run_id)
    started = monotonic()
    logger.info("ingestion started execution_id=%s backend=%s", run_id, backend)
    try:
        yield
    except Exception as error:
        logger.warning(
            "ingestion failed execution_id=%s backend=%s type=%s duration_seconds=%.3f",
            run_id, backend, type(error).__name__, monotonic() - started,
        )
        raise
    else:
        logger.info(
            "ingestion succeeded execution_id=%s backend=%s duration_seconds=%.3f",
            run_id, backend, monotonic() - started,
        )
    finally:
        _execution_id.reset(token)


@contextmanager
def duckdb_writer(database_path: str):
    key = str(Path(database_path).resolve())
    with _locks_guard:
        lock = _writer_locks.setdefault(key, Lock())
    if not lock.acquire(blocking=False):
        raise SnapshotBusyError("Outra ingestão está em andamento. Tente novamente depois.")
    try:
        yield
    finally:
        lock.release()


def validate_candidate(
    raw: pd.DataFrame, silver: pd.DataFrame, gold: pd.DataFrame, scoring_status: str,
) -> None:
    if raw.empty:
        raise RuntimeError("Snapshot candidato vazio.")
    expected_ids = set(raw["id_cliente"])
    expected = raw.rename(columns={
        "id_cliente": "client_identifier", "frequencia": "frequency",
        "recencia_dias": "recency_days", "gasto_total": "total_spend",
        "incidentes": "flight_incidents",
    }).copy()
    expected["tier"] = expected["tier"].str.strip().str.upper()
    expected = expected.set_index("client_identifier").sort_index()
    for frame in (silver, gold):
        required = {
            "client_identifier", "tier", "frequency", "recency_days",
            "total_spend", "flight_incidents",
        }
        if not required.issubset(frame.columns):
            raise RuntimeError("Snapshot candidato com colunas incompletas.")
        ids = frame["client_identifier"]
        if len(frame) != len(raw) or ids.isna().any() or ids.duplicated().any():
            raise RuntimeError("Snapshot candidato com quantidade de clientes inválida.")
        if set(ids) != expected_ids:
            raise RuntimeError("Snapshot candidato com identificadores inconsistentes.")
        actual = frame.set_index("client_identifier").sort_index()[expected.columns]
        if not actual.eq(expected).all().all():
            raise RuntimeError("Snapshot candidato com atributos de clientes inconsistentes.")
    if not {"avg_ticket", "high_risk_flag"}.issubset(gold.columns):
        raise RuntimeError("Snapshot Gold candidato incompleto.")
    if "churn_score" not in gold:
        raise RuntimeError("Snapshot candidato sem scores.")
    scores = pd.to_numeric(gold["churn_score"], errors="coerce")
    if scoring_status in {
        "awaiting_model_registration",
        "awaiting_model_features",
    }:
        valid = gold["churn_score"].isna().all()
    elif scoring_status == "scored":
        valid = np.isfinite(scores).all() and scores.between(0, 1).all()
    else:
        valid = False
    if not valid:
        raise RuntimeError("Snapshot candidato com scores inválidos.")
