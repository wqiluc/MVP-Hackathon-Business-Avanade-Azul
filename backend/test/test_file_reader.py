import pandas as pd
import pytest

from data.ingestion.file_reader import FileReader


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
    expected.to_csv(file_path, index=False)

    result = FileReader.read_file(str(file_path), "csv")

    pd.testing.assert_frame_equal(result, expected)


def test_reads_valid_json(tmp_path):
    file_path = tmp_path / "clients.json"
    expected = pd.DataFrame(VALID_COLUMNS)
    expected.to_json(file_path, orient="records")

    result = FileReader.read_file(str(file_path), "json")

    pd.testing.assert_frame_equal(result, expected)


def test_reads_valid_xlsx(tmp_path):
    file_path = tmp_path / "clients.xlsx"
    expected = pd.DataFrame(VALID_COLUMNS)
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

    with pytest.raises(
        ValueError,
        match=(
            "^Colunas obrigatórias ausentes: frequencia, gasto_total, incidentes, "
            "recencia_dias$"
        ),
    ):
        FileReader.read_file(str(file_path), "csv")
