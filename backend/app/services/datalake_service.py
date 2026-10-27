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
            contract = df_raw.attrs.get("ingestion_contract")
            if contract == "ML_FEATURES_52":
                return cls.score_ml_features(df_raw)
            df_raw = cls._replace_source_ids_with_internal_ids(df_raw)
            if settings.DATA_LAKE_BACKEND == "snowflake":
                from app.services.snowflake_service import SnowflakeDataLake
                resumo = SnowflakeDataLake.process_ingestion(df_raw)
            elif settings.DATA_LAKE_BACKEND == "duckdb":
                resumo = DuckDBDataLake.process_ingestion(df_raw)
            else:
                raise ValueError(
                    f"Backend de Data Lake inválido: {settings.DATA_LAKE_BACKEND!r}. "
                    "Use 'duckdb' ou 'snowflake'."
                )
            return {**resumo, "ingestion_contract": contract} if contract else resumo
        
    @staticmethod
    def score_ml_features(features: pd.DataFrame) -> dict:
        """Score ML_FEATURES_52 and persist results for the local CRM demo."""
        from app.services.ml.churn_service import ChurnService
        from app.services.ml.clv_service import ClvService
        from app.services.ml.feature_builder import FeatureBuilder
        from app.services.ml.inference_provider import ModelInferenceError

        try:
            churn = ChurnService().predict_many(
                FeatureBuilder.build_frame(features, "churn")
            )
            clv = ClvService().predict_many(
                FeatureBuilder.build_frame(features, "clv")
            )
        except ModelInferenceError as error:
            logger.warning("ML scoring failed: %s", error)
            return {
                "status": "unavailable",
                "processed_rows": len(features),
                "ingestion_contract": "ML_FEATURES_52",
                "scoring_status": "unavailable",
                "layers": [],
                "scoring_summary": {},
            }

        scores = [p.score for p in churn]
        values = [p.value for p in clv]

        output = features.copy()

        # Internal identifier used by the local CRM demo.
        if "id_cliente" in output.columns:
            output["client_identifier"] = output["id_cliente"].astype(str)
        else:
            output["client_identifier"] = [
                f"ml-demo-{i + 1:03d}" for i in range(len(output))
            ]

        # ML outputs.
        output["churn_score"] = scores
        output["clv_12m"] = values
        output["clvProjetado"] = output["clv_12m"]
        output["riscoEvasao"] = output["churn_score"]

        # CRM compatibility fields.
        output["tier"] = output["tier_idx"].map(
            {
                0: "Básico",
                1: "Topázio",
                2: "Safira",
                3: "Diamante",
            }
        ).fillna("Básico")

        output["frequency"] = output["voos_12m"]
        output["recency_days"] = output["dias_desde_ultimo_voo"]
        output["total_spend"] = output["gasto_total_12m"]
        output["flight_incidents"] = output["n_cancelamentos_12m"]
        output["avg_ticket"] = output["ticket_medio_12m"]

        # Persist local CRM snapshot.
        with duckdb_writer(settings.DUCKDB_PATH):
            conn = DataLakeService.get_connection()
            try:
                DuckDBAdapter.init_schema(conn)
                DuckDBAdapter.write_gold(conn, output)

                conn.execute(
                    """
                    CREATE OR REPLACE TABLE gold.snapshot_publication AS
                    SELECT
                        ? AS execution_id,
                        CURRENT_TIMESTAMP AS published_at
                    """,
                    [execution_id()],
                )
            finally:
                conn.close()

        return {
            "status": "success",
            "processed_rows": len(output),
            "ingestion_contract": "ML_FEATURES_52",
            "scoring_status": "scored",
            "layers": [
                "gold.client_features",
                "gold.snapshot_publication",
            ],
            "scoring_summary": {
                "churn_score_mean": sum(scores) / len(scores),
                "churn_score_max": max(scores),
                "clv_mean": sum(values) / len(values),
                "model_versions": {
                    "churn": (
                        f"{churn[0].model_name}:"
                        f"{churn[0].model_version}"
                    ),
                    "clv": (
                        f"{clv[0].model_name}:"
                        f"{clv[0].model_version}"
                    ),
                },
            },
        }
 
    # @staticmethod
    # def score_ml_features(features: pd.DataFrame) -> dict:
    #     """Score ML_FEATURES_52 uploads with the official models; nothing is persisted
    #     or published to the CRM snapshot, and no per-client output is returned."""
    #     from app.services.ml.churn_service import ChurnService
    #     from app.services.ml.clv_service import ClvService
    #     from app.services.ml.feature_builder import FeatureBuilder

    #     from app.services.ml.inference_provider import ModelInferenceError

    #     def run(service, kind: str):
    #         try:
    #             return service().predict_many(FeatureBuilder.build_frame(features, kind))
    #         except ModelInferenceError:
    #             return None

    #     churn = run(ChurnService, "churn")
    #     clv = run(ClvService, "clv")
    #     summary: dict = {"churn_score_mean": None, "churn_score_max": None, "clv_mean": None}
    #     versions: dict = {}
    #     if churn:
    #         scores = [p.score for p in churn]
    #         summary.update(churn_score_mean=sum(scores) / len(scores), churn_score_max=max(scores))
    #         versions["churn"] = f"{churn[0].model_name}:{churn[0].model_version}"
    #     if clv:
    #         values = [p.value for p in clv]
    #         summary["clv_mean"] = sum(values) / len(values)
    #         versions["clv"] = f"{clv[0].model_name}:{clv[0].model_version}"
    #     summary["model_versions"] = versions
    #     available = [m for m, r in (("churn", churn), ("clv", clv)) if r]
    #     status = "scored" if len(available) == 2 else ("partial" if available else "unavailable")
    #     return {
    #         "status": "scored_not_persisted",
    #         "processed_rows": len(features),
    #         "ingestion_contract": "ML_FEATURES_52",
    #         "scoring_status": status,
    #         "layers": [],
    #         "scoring_summary": summary,
    #     }

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
