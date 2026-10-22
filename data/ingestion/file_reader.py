import csv
from datetime import date

import numpy as np
import pandas as pd


class FileContractError(ValueError):
    def __init__(
        self,
        message: str,
        *,
        missing_columns: list[str] | None = None,
        invalid_columns: list[str] | None = None,
    ) -> None:
        super().__init__(message)
        self.missing_columns = missing_columns or []
        self.invalid_columns = invalid_columns or []


class FileReader:
    MAX_ROWS = 100_000
    MAX_INTEGER = 2_147_483_647
    VALID_TIERS = {"BASICO", "BÁSICO", "TOPAZIO", "TOPÁZIO", "SAFIRA", "DIAMANTE"}
    CANONICAL_COLUMNS = (
        "id_cliente",
        "tier",
        "frequencia",
        "recencia_dias",
        "gasto_total",
        "incidentes",
    )
    SYNTHETIC_COLUMNS = {
        "CUSTOMER_ID",
        "CATEGORIA_TIER",
        "PONTOS_ACUMULADOS",
        "VOOS_ANO",
        "DATA_CADASTRO",
    }
    SYNTHETIC_REFERENCE_DATE = date(2026, 9, 30)
    QUALIFYING_POINTS_PER_REAL = 0.4

    @classmethod
    def read_file(cls, file_path: str, file_type: str) -> pd.DataFrame:
        if file_type in ("xlsx", "xls"):
            df = pd.read_excel(file_path, dtype=object)
        elif file_type == "csv":
            df = cls._read_csv(file_path)
        elif file_type == "json":
            df = pd.read_json(file_path, dtype=False)
        else:
            raise ValueError("Formato não suportado. Envie arquivos Excel, CSV ou JSON.")

        if df.empty:
            raise FileContractError("O arquivo enviado está vazio.")
        if len(df) > cls.MAX_ROWS:
            raise FileContractError(f"O arquivo excede o limite de {cls.MAX_ROWS} clientes.")

        normalized_columns = [str(column).strip().upper() for column in df.columns]
        if len(set(normalized_columns)) != len(normalized_columns):
            raise FileContractError(
                "O arquivo contém nomes de coluna duplicados.",
                invalid_columns=normalized_columns,
            )
        df.columns = normalized_columns

        if set(cls.CANONICAL_COLUMNS).issubset(
            {column.lower() for column in normalized_columns}
        ):
            if tuple(column.lower() for column in normalized_columns) != cls.CANONICAL_COLUMNS:
                raise FileContractError(
                    "O cabeçalho deve conter somente as seis colunas canônicas, na ordem documentada.",
                    invalid_columns=sorted(
                        {column.lower() for column in normalized_columns}
                        - set(cls.CANONICAL_COLUMNS)
                    ),
                )
            canonical = df.rename(columns=str.lower).loc[:, cls.CANONICAL_COLUMNS].copy()
        elif cls.SYNTHETIC_COLUMNS.issubset(set(normalized_columns)):
            canonical = cls._adapt_synthetic_dataset(df)
        else:
            canonical_names = set(cls.CANONICAL_COLUMNS)
            canonical_present = {column.lower() for column in normalized_columns}
            canonical_missing = sorted(canonical_names - canonical_present)
            synthetic_missing = sorted(cls.SYNTHETIC_COLUMNS - set(normalized_columns))
            raise FileContractError(
                "Arquivo incompatível com o contrato de ingestão. "
                f"Colunas canônicas ausentes: {', '.join(canonical_missing)}. "
                "Ou forneça o formato sintético com: "
                f"{', '.join(synthetic_missing)}.",
                missing_columns=canonical_missing,
            )

        return cls._validate_canonical(canonical)

    @classmethod
    def _read_csv(cls, file_path: str) -> pd.DataFrame:
        try:
            with open(file_path, encoding="utf-8-sig", newline="") as source:
                sample = source.readline()
                if not sample:
                    raise FileContractError("O arquivo enviado está vazio.")
                try:
                    dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
                except csv.Error:
                    dialect = csv.excel
                source.seek(0)
                reader = csv.reader(source, dialect=dialect, strict=True)
                header = next(reader)
                rows = []
                for row in reader:
                    if not row:
                        continue
                    if len(row) != len(header):
                        raise FileContractError("CSV malformado: quantidade de campos inconsistente.")
                    rows.append(row)
                    if len(rows) > cls.MAX_ROWS:
                        raise FileContractError(f"O arquivo excede o limite de {cls.MAX_ROWS} clientes.")
                return pd.DataFrame(rows, columns=header)
        except (csv.Error, UnicodeError) as error:
            raise FileContractError("CSV malformado ou codificação inválida; utilize UTF-8.") from error

    @classmethod
    def _adapt_synthetic_dataset(cls, source: pd.DataFrame) -> pd.DataFrame:
        signup_dates = pd.to_datetime(source["DATA_CADASTRO"], errors="coerce")
        if signup_dates.isna().any():
            raise FileContractError(
                "DATA_CADASTRO contém datas ausentes ou inválidas.",
                invalid_columns=["DATA_CADASTRO"],
            )

        signup_days = signup_dates.dt.date
        future_dates = signup_days.map(lambda value: value > cls.SYNTHETIC_REFERENCE_DATE)
        if future_dates.any():
            raise FileContractError(
                "DATA_CADASTRO contém datas posteriores à referência sintética "
                f"{cls.SYNTHETIC_REFERENCE_DATE.isoformat()}.",
                invalid_columns=["DATA_CADASTRO"],
            )

        points = pd.to_numeric(source["PONTOS_ACUMULADOS"], errors="coerce")
        if points.isna().any() or (points < 0).any():
            raise FileContractError(
                "PONTOS_ACUMULADOS deve conter números não negativos.",
                invalid_columns=["PONTOS_ACUMULADOS"],
            )

        recency = (
            source["RECENCIA_DIAS"]
            if "RECENCIA_DIAS" in source
            else signup_days.map(
                lambda value: (cls.SYNTHETIC_REFERENCE_DATE - value).days
            )
        )
        spend = (
            source["GASTO_TOTAL"]
            if "GASTO_TOTAL" in source
            else (points / cls.QUALIFYING_POINTS_PER_REAL).round(2)
        )
        incidents = source["INCIDENTES"] if "INCIDENTES" in source else 0
        return pd.DataFrame(
            {
                "id_cliente": source["CUSTOMER_ID"],
                "tier": source["CATEGORIA_TIER"],
                "frequencia": source["VOOS_ANO"],
                "recencia_dias": recency,
                "gasto_total": spend,
                "incidentes": incidents,
            }
        )

    @classmethod
    def _validate_canonical(cls, df: pd.DataFrame) -> pd.DataFrame:
        if df["id_cliente"].map(lambda value: isinstance(value, (dict, list, bool))).any():
            raise FileContractError(
                "id_cliente deve ser um identificador simples.", invalid_columns=["id_cliente"],
            )
        if df["id_cliente"].isna().any() or df["id_cliente"].astype(str).str.strip().eq("").any():
            raise FileContractError(
                "id_cliente não pode estar vazio.",
                invalid_columns=["id_cliente"],
            )
        if df["tier"].isna().any() or df["tier"].astype(str).str.strip().eq("").any():
            raise FileContractError("tier não pode estar vazio.", invalid_columns=["tier"])
        if not df["tier"].astype(str).str.strip().str.upper().isin(cls.VALID_TIERS).all():
            raise FileContractError(
                "tier deve ser Básico, Topázio, Safira ou Diamante.",
                invalid_columns=["tier"],
            )

        for column in cls.CANONICAL_COLUMNS[2:]:
            df[column] = cls._validate_numeric_column(df[column], column)

        df["id_cliente"] = df["id_cliente"].astype(str).str.strip()
        if df["id_cliente"].duplicated().any():
            raise FileContractError(
                "id_cliente deve ser único por snapshot.",
                invalid_columns=["id_cliente"],
            )
        if df["id_cliente"].str.contains(r"[\x00-\x1f\x7f]", regex=True).any():
            raise FileContractError(
                "id_cliente contém caracteres de controle inválidos.",
                invalid_columns=["id_cliente"],
            )
        df["tier"] = df["tier"].astype(str).str.strip()
        return df

    @classmethod
    def _validate_numeric_column(cls, source: pd.Series, column: str) -> pd.Series:
        if source.map(lambda value: isinstance(value, bool)).any():
            raise FileContractError(
                f"{column} não pode conter valores booleanos.", invalid_columns=[column],
            )
        values = pd.to_numeric(source, errors="coerce")
        if values.isna().any() or not np.isfinite(values).all():
            raise FileContractError(
                f"{column} deve conter somente valores numéricos finitos.",
                invalid_columns=[column],
            )
        if (values < 0).any():
            raise FileContractError(
                f"{column} não pode conter valores negativos.", invalid_columns=[column],
            )
        if column != "gasto_total" and (
            values.mod(1).ne(0).any() or values.gt(cls.MAX_INTEGER).any()
        ):
            raise FileContractError(
                f"{column} deve conter inteiros entre 0 e {cls.MAX_INTEGER}.",
                invalid_columns=[column],
            )
        return values
