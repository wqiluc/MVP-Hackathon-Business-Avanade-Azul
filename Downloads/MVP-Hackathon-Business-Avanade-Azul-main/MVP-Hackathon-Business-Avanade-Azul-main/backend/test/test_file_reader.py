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


@pytest.mark.parametrize("column,value", [
    ("id_cliente", ""), ("id_cliente", " \t "), ("id_cliente", "c\x00bad"),
    ("tier", "OURO"), ("tier", ""), ("frequencia", "text"),
    ("frequencia", 1.5), ("frequencia", -1), ("frequencia", 2_147_483_648),
    ("recencia_dias", -1), ("recencia_dias", 1.5),
    ("gasto_total", -1), ("gasto_total", "Infinity"), ("gasto_total", "NaN"),
    ("incidentes", 0.5), ("incidentes", -1),
])
def test_rejects_invalid_canonical_values(tmp_path, column, value):
    frame = pd.DataFrame(VALID_COLUMNS).astype(object)
    frame.loc[0, column] = value
    path = tmp_path / "invalid.csv"
    frame.to_csv(path, index=False)
    with pytest.raises(FileContractError) as error:
        FileReader.read_file(str(path), "csv")
    assert error.value.invalid_columns == [column]


@pytest.mark.parametrize("content", [
    "id_cliente,tier,frequencia,recencia_dias,gasto_total,incidentes,extra\nc,Diamante,1,2,3,0,x\n",
    "tier,id_cliente,frequencia,recencia_dias,gasto_total,incidentes\nDiamante,c,1,2,3,0\n",
    "id_cliente,tier,frequencia,recencia_dias,gasto_total,incidentes,id_cliente\nc,Diamante,1,2,3,0,c\n",
    "id_cliente,tier,frequencia,recencia_dias,gasto_total,incidentes\nc,Diamante,1,2,3,0,extra\n",
    'id_cliente,tier,frequencia,recencia_dias,gasto_total,incidentes\n"unclosed,Diamante,1,2,3,0\n',
])
def test_rejects_extra_reordered_duplicate_or_malformed_csv_columns(tmp_path, content):
    path = tmp_path / "invalid-header.csv"
    path.write_text(content, encoding="utf-8")
    with pytest.raises(FileContractError):
        FileReader.read_file(str(path), "csv")


def test_preserves_leading_zero_identifiers(tmp_path):
    path = tmp_path / "identifiers.csv"
    path.write_text(
        ",".join(FileReader.CANONICAL_COLUMNS) + "\n0001,Diamante,1,2,3,0\n",
        encoding="utf-8",
    )
    assert FileReader.read_file(str(path), "csv")["id_cliente"].tolist() == ["0001"]


def test_duplicate_ids_are_rejected_after_trimming(tmp_path):
    frame = pd.DataFrame(VALID_COLUMNS)
    frame = pd.concat([frame, frame], ignore_index=True)
    frame["id_cliente"] = ["c-1", " c-1 "]
    path = tmp_path / "duplicates.csv"
    frame.to_csv(path, index=False)
    with pytest.raises(FileContractError, match="único"):
        FileReader.read_file(str(path), "csv")


@pytest.mark.parametrize("kind", ["csv", "json", "xlsx"])
def test_row_limit_is_enforced_at_boundary(tmp_path, monkeypatch, kind):
    monkeypatch.setattr(FileReader, "MAX_ROWS", 2)
    path = tmp_path / f"volume.{kind}"
    frame = pd.concat([pd.DataFrame(VALID_COLUMNS)] * 3, ignore_index=True)
    frame["id_cliente"] = ["c-1", "c-2", "c-3"]
    writer = {
        "csv": lambda data: data.to_csv(path, index=False),
        "json": lambda data: data.to_json(path, orient="records"),
        "xlsx": lambda data: data.to_excel(path, index=False),
    }[kind]
    writer(frame.iloc[:2])
    assert len(FileReader.read_file(str(path), kind)) == 2
    writer(frame)
    with pytest.raises(FileContractError, match="limite de 2"):
        FileReader.read_file(str(path), kind)


def test_json_boolean_is_not_a_numeric_feature(tmp_path):
    frame = pd.DataFrame(VALID_COLUMNS)
    frame["frequencia"] = True
    path = tmp_path / "bool.json"
    frame.to_json(path, orient="records")
    with pytest.raises(FileContractError, match="booleanos"):
        FileReader.read_file(str(path), "json")


def test_default_100000_row_limit_accepts_boundary_and_rejects_next_row(tmp_path):
    assert FileReader.MAX_ROWS == 100_000
    path = tmp_path / "default-volume.csv"
    with path.open("w", encoding="utf-8") as output:
        output.write(",".join(FileReader.CANONICAL_COLUMNS) + "\n")
        for index in range(100_000):
            output.write(f"C-{index},Diamante,1,2,3,0\n")
    assert len(FileReader.read_file(str(path), "csv")) == 100_000
    with path.open("a", encoding="utf-8") as output:
        output.write("C-100000,Diamante,1,2,3,0\n")
    with pytest.raises(FileContractError, match="limite de 100000"):
        FileReader.read_file(str(path), "csv")
