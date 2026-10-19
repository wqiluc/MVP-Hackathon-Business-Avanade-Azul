import pandas as pd
import pytest

from data.ingestion.file_reader import FileContractError, FileReader


VALID_COLUMNS = {
    "id_cliente": [1],
    "tier": ["DIAMANTE"],
    "frequencia": [12],
    "recencia_dias": [30],
    "gasto_total": [15000],
    "incidentes": [1],
}


def test_reads_valid_csv(tmp_path):
    file_path = tmp_path / "clients.csv"
    expected = pd.DataFrame(VALID_COLUMNS)
    expected["id_cliente"] = expected["id_cliente"].astype(str)
    expected.to_csv(file_path, index=False)

    result = FileReader.read_file(str(file_path), "csv")

    pd.testing.assert_frame_equal(result, expected)


def test_reads_valid_json(tmp_path):
    file_path = tmp_path / "clients.json"
    expected = pd.DataFrame(VALID_COLUMNS)
    expected["id_cliente"] = expected["id_cliente"].astype(str)
    expected.to_json(file_path, orient="records")

    result = FileReader.read_file(str(file_path), "json")

    pd.testing.assert_frame_equal(result, expected)


def test_reads_valid_xlsx(tmp_path):
    file_path = tmp_path / "clients.xlsx"
    expected = pd.DataFrame(VALID_COLUMNS)
    expected["id_cliente"] = expected["id_cliente"].astype(str)
    expected.to_excel(file_path, index=False)

    result = FileReader.read_file(str(file_path), "xlsx")

    pd.testing.assert_frame_equal(result, expected)


def test_rejects_empty_dataframe_after_column_validation(tmp_path):
    file_path = tmp_path / "empty.csv"
    pd.DataFrame(columns=VALID_COLUMNS).to_csv(file_path, index=False)

    with pytest.raises(ValueError, match="^O arquivo enviado está vazio\\.$"):
        FileReader.read_file(str(file_path), "csv")


def test_rejects_unsupported_file_type():
    with pytest.raises(
        ValueError,
        match="^Formato não suportado\\. Envie arquivos Excel, CSV ou JSON\\.$",
    ):
        FileReader.read_file("unused.txt", "txt")


def test_propagates_missing_file_error(tmp_path):
    file_path = tmp_path / "missing.csv"

    with pytest.raises(FileNotFoundError):
        FileReader.read_file(str(file_path), "csv")


def test_rejects_missing_required_columns_in_sorted_order(tmp_path):
    file_path = tmp_path / "missing-columns.csv"
    pd.DataFrame({"id_cliente": [1], "tier": ["DIAMANTE"]}).to_csv(file_path, index=False)

    with pytest.raises(FileContractError) as error:
        FileReader.read_file(str(file_path), "csv")
    assert error.value.missing_columns == [
        "frequencia",
        "gasto_total",
        "incidentes",
        "recencia_dias",
    ]


def test_adapts_synthetic_dataset_and_drops_unapproved_columns(tmp_path):
    file_path = tmp_path / "synthetic.csv"
    pd.DataFrame(
        {
            "CUSTOMER_ID": ["C-001"],
            "NOME": ["Synthetic Name"],
            "EMAIL": ["synthetic@example.invalid"],
            "ESTADO": ["SP"],
            "CATEGORIA_TIER": ["Safira"],
            "PONTOS_ACUMULADOS": [400],
            "VOOS_ANO": [12],
            "RISCO_CHURN": [1],
            "DATA_CADASTRO": ["2025-09-30"],
        }
    ).to_csv(file_path, index=False)

    result = FileReader.read_file(str(file_path), "csv")

    assert result.to_dict(orient="records") == [
        {
            "id_cliente": "C-001",
            "tier": "Safira",
            "frequencia": 12,
            "recencia_dias": 365,
            "gasto_total": 1000.0,
            "incidentes": 0,
        }
    ]
    assert "NOME" not in result.columns
    assert "EMAIL" not in result.columns
    assert "RISCO_CHURN" not in result.columns


def test_synthetic_adapter_uses_only_explicit_safe_feature_columns(tmp_path):
    file_path = tmp_path / "synthetic-with-features.csv"
    pd.DataFrame(
        {
            "CUSTOMER_ID": ["C-001"],
            "CATEGORIA_TIER": ["Topázio"],
            "PONTOS_ACUMULADOS": [200],
            "VOOS_ANO": [4],
            "DATA_CADASTRO": ["2025-01-01"],
            "RISCO_CHURN": [0],
            "RECENCIA_DIAS": [23],
            "GASTO_TOTAL": [875.5],
            "INCIDENTES": [2],
        }
    ).to_csv(file_path, index=False)

    result = FileReader.read_file(str(file_path), "csv")

    assert result.loc[0, ["recencia_dias", "gasto_total", "incidentes"]].tolist() == [
        23.0,
        875.5,
        2.0,
    ]
