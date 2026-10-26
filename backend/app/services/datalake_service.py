import pandas as pd
from app.config import settings
from app.core.security import anonymize_identifier
from app.services.snapshot import (
    duckdb_writer, execution_id, ingestion_run, logger, validate_candidate,
)
from data.bronze.duckdb_writer import DuckDBBronzeWriter
from data.gold.duckdb_transformer import DuckDBGoldTransformer
from data.ingestion.file_reader import FileReader
from data.silver.duckdb_transformer import DuckDBSilverTransformer
from data.storage.duckdb_adapter import DuckDBAdapter


class DuckDBDataLake:
    @staticmethod
    def process_ingestion(df_raw: pd.DataFrame) -> dict:
        with duckdb_writer(settings.DUCKDB_PATH):
            conn = DataLakeService.get_connection()
            run_id = execution_id()
            try:
                conn.execute("BEGIN TRANSACTION")
                try:
                    DuckDBAdapter.init_schema(conn)
                    DuckDBBronzeWriter.write_raw_clients(conn, df_raw)
                    DuckDBSilverTransformer.transform_cleaned_clients(conn)
                    DuckDBGoldTransformer.transform_client_features(conn)
                    scoring_status = DataLakeService._score_gold(conn)
                    silver = conn.execute("SELECT * FROM silver.cleaned_clients").fetchdf()
                    gold = conn.execute("SELECT * FROM gold.client_features").fetchdf()
                    validate_candidate(df_raw, silver, gold, scoring_status)
                    conn.execute("""
                        CREATE OR REPLACE TABLE gold.snapshot_publication AS
                        SELECT ? AS execution_id, CURRENT_TIMESTAMP AS published_at
                    """, [run_id])
                    conn.execute("COMMIT")
                except Exception:
                    conn.execute("ROLLBACK")
                    logger.warning("snapshot rolled_back execution_id=%s backend=duckdb", run_id)
                    raise
                logger.info("snapshot published execution_id=%s backend=duckdb", run_id)
                return {
                    "status": "success",
                    "processed_rows": len(gold),
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
        with ingestion_run(settings.DATA_LAKE_BACKEND):
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
        """Score only with the real 52-feature artifact; never derive missing inputs."""
        from app.services.ml.churn_service import ChurnService
        from app.services.ml.feature_builder import (
            FeatureBuilder,
            MissingModelFeaturesError,
        )

        try:
            features = FeatureBuilder.build_frame(df, "churn")
        except MissingModelFeaturesError as error:
            logger.info(
                "Real churn scoring unavailable: required source features are absent "
                "missing_feature_count=%s",
                len(error.missing),
            )
            return [float("nan")] * len(df), "awaiting_model_features"
        if not features:
            return [], "scored"
        predictions = ChurnService().predict_many(features)
        return [prediction.score for prediction in predictions], "scored"

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
