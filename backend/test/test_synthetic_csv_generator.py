import subprocess
import sys
from pathlib import Path

import pandas as pd

from data.ingestion.file_reader import FileReader


PROJECT_ROOT = Path(__file__).resolve().parents[2]
GENERATOR = PROJECT_ROOT / "scripts" / "generate_synthetic_clients.py"
CANONICAL_COLUMNS = [
    "id_cliente",
    "tier",
    "frequencia",
    "recencia_dias",
    "gasto_total",
    "incidentes",
]


def test_development_generator_outputs_exact_valid_ingestion_contract(tmp_path):
    output_path = tmp_path / "synthetic_clients.csv"
    subprocess.run(
        [
            sys.executable,
            str(GENERATOR),
            "--output",
            str(output_path),
            "--rows",
            "8",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    raw = pd.read_csv(output_path)
    assert raw.columns.tolist() == CANONICAL_COLUMNS
    assert len(raw) == 8
    assert raw["id_cliente"].notna().all()
    assert raw["tier"].notna().all()
    assert set(raw["tier"]) <= {"Básico", "Topázio", "Safira", "Diamante"}
    for column in CANONICAL_COLUMNS[2:]:
        assert pd.api.types.is_numeric_dtype(raw[column])
        assert raw[column].notna().all()
        assert (raw[column] >= 0).all()
    assert "CUSTOMER_ID" not in raw.columns

    normalized = FileReader.read_file(str(output_path), "csv")
    assert normalized.columns.tolist() == CANONICAL_COLUMNS
    assert len(normalized) == 8
    assert normalized["id_cliente"].str.startswith("synthetic-").all()
