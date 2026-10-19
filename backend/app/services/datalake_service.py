import pandas as pd
from app.config import settings
from app.core.security import anonymize_identifier
from data.bronze.duckdb_writer import DuckDBBronzeWriter
from data.gold.duckdb_transformer import DuckDBGoldTransformer
from data.ingestion.file_reader import FileReader
from data.silver.duckdb_transformer import DuckDBSilverTransformer
from data.storage.duckdb_adapter import DuckDBAdapter


class DuckDBDataLake:
    @staticmethod
    def process_ingestion(df_raw: pd.DataFrame) -> dict:
        conn = DataLakeService.get_connection()
        try:
            DuckDBBronzeWriter.write_raw_clients(conn, df_raw)
            DuckDBSilverTransformer.transform_cleaned_clients(conn)
            DuckDBGoldTransformer.transform_client_features(conn)
            scoring_status = DataLakeService._score_gold(conn)
            row_count = conn.execute(
                "SELECT COUNT(*) FROM gold.client_features"
            ).fetchone()[0]
            return {
                "status": "success",
                "processed_rows": row_count,
                "scoring_status": scoring_status,
                "layers": [
                    "bronze.raw_clients",
                    "silver.cleaned_clients",
                    "gold.client_features",
                ],
            }
        finally:
            conn.close()

    @staticmethod
    def read_gold() -> pd.DataFrame:
        conn = DataLakeService.get_connection()
        try:
            return DuckDBAdapter.read_gold(conn)
        finally:
            conn.close()


class DataLakeService:
    @staticmethod
    def get_connection():
        return DuckDBAdapter.connect(settings.DUCKDB_PATH)

    @classmethod
    def init_schema(cls):
        """Cria as camadas Medalhão (Bronze, Silver, Gold)."""
        conn = cls.get_connection()
        try:
            DuckDBAdapter.init_schema(conn)
        finally:
            conn.close()

    @classmethod
    def process_ingestion(cls, file_path: str, file_type: str) -> dict:
        df_raw = cls._ler_arquivo(file_path, file_type)
        if df_raw.empty:
            raise ValueError("O arquivo enviado está vazio.")
        df_raw = cls._replace_source_ids_with_internal_ids(df_raw)

        if settings.DATA_LAKE_BACKEND == "snowflake":
            from app.services.snowflake_service import SnowflakeDataLake
            return SnowflakeDataLake.process_ingestion(df_raw)
        if settings.DATA_LAKE_BACKEND == "duckdb":
            return DuckDBDataLake.process_ingestion(df_raw)
        raise ValueError(
            f"Backend de Data Lake inválido: {settings.DATA_LAKE_BACKEND!r}. "
            "Use 'duckdb' ou 'snowflake'."
        )

    @staticmethod
    def _replace_source_ids_with_internal_ids(df_raw: pd.DataFrame) -> pd.DataFrame:
        result = df_raw.copy()

        def pseudonymize(source_id: object) -> object:
            if pd.isna(source_id):
                return source_id
            return anonymize_identifier(str(source_id))

        result["id_cliente"] = result["id_cliente"].map(pseudonymize)
        return result

    @staticmethod
    def _ler_arquivo(file_path: str, file_type: str) -> pd.DataFrame:
        return FileReader.read_file(file_path, file_type)

    @classmethod
    def _score_gold(cls, conn) -> str:
        df = conn.execute("SELECT * FROM gold.client_features").fetchdf()
        df["churn_score"], scoring_status = cls.score_gold(df)
        DuckDBAdapter.write_gold(conn, df)
        return scoring_status

    @staticmethod
    def score_gold(df: pd.DataFrame) -> tuple[list[float], str]:
        """Score Gold only after a registry alias exists; never substitute a heuristic."""
        from ml.models.mlflow_tracker import configure_tracking, get_active_churn_model

        configure_tracking(settings.MLFLOW_TRACKING_URI)
        if get_active_churn_model() is None:
            return [float("nan")] * len(df), "awaiting_model_registration"

        from app.services.inference_service import predict_churn

        return predict_churn(df), "scored"

    @classmethod
    def read_gold(cls) -> pd.DataFrame:
        """Lê a camada Ouro (vazia se ainda não houve ingestão)."""
        if settings.DATA_LAKE_BACKEND == "snowflake":
            from app.services.snowflake_service import SnowflakeDataLake
            return SnowflakeDataLake.read_gold()
        if settings.DATA_LAKE_BACKEND == "duckdb":
            return DuckDBDataLake.read_gold()
        raise ValueError(
            f"Backend de Data Lake inválido: {settings.DATA_LAKE_BACKEND!r}. "
            "Use 'duckdb' ou 'snowflake'."
        )
