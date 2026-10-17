import pandas as pd


class FileReader:
    REQUIRED_COLUMNS = {
        "id_cliente",
        "tier",
        "frequencia",
        "recencia_dias",
        "gasto_total",
        "incidentes",
    }

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

        missing_columns = cls.REQUIRED_COLUMNS - set(df.columns)
        if missing_columns:
            raise ValueError(
                f"Colunas obrigatórias ausentes: {', '.join(sorted(missing_columns))}"
            )
        if df.empty:
            raise ValueError("O arquivo enviado está vazio.")
        return df
