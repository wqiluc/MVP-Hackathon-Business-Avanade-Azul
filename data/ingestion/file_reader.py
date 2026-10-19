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
            df = pd.read_excel(file_path)
        elif file_type == "csv":
            df = pd.read_csv(file_path, sep=None, engine="python")
        elif file_type == "json":
            df = pd.read_json(file_path)
        else:
            raise ValueError("Formato não suportado. Envie arquivos Excel, CSV ou JSON.")

        if df.empty:
            raise FileContractError("O arquivo enviado está vazio.")

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
                f"{', '.join(sorted(synthetic_missing))}.",
                missing_columns=canonical_missing,
            )

        return cls._validate_canonical(canonical)

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
        if df["id_cliente"].isna().any() or df["id_cliente"].astype(str).str.strip().eq("").any():
            raise FileContractError(
                "id_cliente não pode estar vazio.",
                invalid_columns=["id_cliente"],
            )
        if df["tier"].isna().any() or df["tier"].astype(str).str.strip().eq("").any():
            raise FileContractError("tier não pode estar vazio.", invalid_columns=["tier"])

        for column in cls.CANONICAL_COLUMNS[2:]:
            values = pd.to_numeric(df[column], errors="coerce")
            if values.isna().any() or not np.isfinite(values).all():
                raise FileContractError(
                    f"{column} deve conter somente valores numéricos finitos.",
                    invalid_columns=[column],
                )
            if (values < 0).any():
                raise FileContractError(
                    f"{column} não pode conter valores negativos.",
                    invalid_columns=[column],
                )
            df[column] = values

        df["id_cliente"] = df["id_cliente"].astype(str).str.strip()
        df["tier"] = df["tier"].astype(str).str.strip()
        return df
