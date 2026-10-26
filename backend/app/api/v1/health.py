from urllib.parse import quote, urlparse, urlunparse

import requests
from redis.exceptions import RedisError
from fastapi import APIRouter, HTTPException, status

from app.config import settings
from app.core.ai_rate_limit import redis_client, validate_ai_rate_limit_settings

router = APIRouter()
_DEPENDENCY_TIMEOUT_SECONDS = 2


@router.get("/")
def check_health():
    return {
        "status": "online",
        "service": "CRM de Alto Valor",
        "version": "2.0.0"
    }


@router.get("/live")
def liveness():
    return {"status": "alive"}


def _check_duckdb() -> str:
    conn = None
    try:
        from data.storage.duckdb_adapter import DuckDBAdapter

        conn = DuckDBAdapter.connect(settings.DUCKDB_PATH)
        result = conn.execute("SELECT 1").fetchone()
        return "ready" if result and result[0] == 1 else "failed"
    except Exception:
        return "failed"
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


def _check_snowflake() -> str:
    conn = None
    cursor = None
    try:
        from app.services.snowflake_service import SnowflakeDataLake

        conn = SnowflakeDataLake.get_connection(
            login_timeout=_DEPENDENCY_TIMEOUT_SECONDS,
            network_timeout=_DEPENDENCY_TIMEOUT_SECONDS,
            statement_timeout=_DEPENDENCY_TIMEOUT_SECONDS,
        )
        cursor = conn.cursor()
        result = cursor.execute(
            "SELECT 1", timeout=_DEPENDENCY_TIMEOUT_SECONDS
        ).fetchone()
        return "ready" if result and result[0] == 1 else "failed"
    except Exception:
        return "failed"
    finally:
        if cursor is not None:
            try:
                cursor.close()
            except Exception:
                pass
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


def _health_url(uri: str, endpoint: str) -> str | None:
    try:
        parsed = urlparse(uri.strip())
    except ValueError:
        return None
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None
    path = parsed.path.rstrip("/")
    if endpoint == "ping":
        if path.endswith("/invocations"):
            path = path[: -len("/invocations")]
        elif path:
            return None
    health_path = f"{path}/{endpoint}" if path else f"/{endpoint}"
    return urlunparse((parsed.scheme, parsed.netloc, health_path, "", "", ""))


def _check_http_health(uri: str, endpoint: str) -> str:
    health_url = _health_url(uri, endpoint)
    if health_url is None:
        return "unverified"
    try:
        response = requests.get(
            health_url,
            timeout=_DEPENDENCY_TIMEOUT_SECONDS,
            allow_redirects=False,
        )
        return "ready" if response.status_code == 200 else "failed"
    except Exception:
        return "failed"


def _check_databricks_endpoint(host: str, token: str, endpoint: str) -> str:
    parsed = urlparse(host.strip())
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.netloc
        or parsed.path not in {"", "/"}
        or parsed.query
        or parsed.fragment
        or not token.strip()
        or not endpoint.strip()
    ):
        return "unverified"
    url = (
        f"{parsed.scheme}://{parsed.netloc}/api/2.0/serving-endpoints/"
        f"{quote(endpoint.strip(), safe='')}"
    )
    try:
        response = requests.get(
            url,
            headers={"Authorization": f"Bearer {token}"},
            timeout=_DEPENDENCY_TIMEOUT_SECONDS,
            allow_redirects=False,
        )
        if response.status_code != 200:
            return "failed"
        body = response.json()
        return (
            "ready"
            if isinstance(body, dict)
            and isinstance(body.get("state"), dict)
            and body["state"].get("ready") == "READY"
            else "failed"
        )
    except (requests.RequestException, ValueError):
        return "failed"


def _check_redis() -> str:
    try:
        validate_ai_rate_limit_settings()
        if not settings.REDIS_URL:
            return "failed"
        return "ready" if redis_client(settings.REDIS_URL).ping() else "failed"
    except (RedisError, RuntimeError, ValueError):
        return "failed"


@router.get("/ready")
def readiness():
    checks = {
        "data_lake_backend": settings.DATA_LAKE_BACKEND in {"duckdb", "snowflake"},
        "mlflow_tracking_configured": bool(settings.MLFLOW_TRACKING_URI.strip()),
        "ml_inference_mode_configured": settings.ML_INFERENCE_MODE
        in {"local", "databricks"},
        "upload_limit_configured": settings.MAX_UPLOAD_BYTES > 0,
    }
    dependencies = {}
    if settings.DATA_LAKE_BACKEND == "duckdb":
        dependencies["data_lake"] = _check_duckdb()
    elif settings.DATA_LAKE_BACKEND == "snowflake":
        checks["snowflake_credentials_configured"] = all(
            str(value or "").strip()
            for value in (
                settings.SNOWFLAKE_ACCOUNT,
                settings.SNOWFLAKE_USER,
                settings.SNOWFLAKE_PASSWORD,
                settings.SNOWFLAKE_DATABASE,
                settings.SNOWFLAKE_WAREHOUSE,
            )
        )
        dependencies["data_lake"] = (
            _check_snowflake()
            if checks["snowflake_credentials_configured"]
            else "failed"
        )
    else:
        dependencies["data_lake"] = "unverified"

    if settings.ML_INFERENCE_MODE == "local":
        dependencies["ml_inference"] = (
            "configured"
            if settings.ML_CHURN_MODEL_PATH.strip()
            and settings.ML_CLV_MODEL_PATH.strip()
            else "not_configured"
        )
    elif settings.ML_INFERENCE_MODE == "databricks":
        endpoint_statuses = [
            _check_databricks_endpoint(
                settings.DATABRICKS_HOST,
                settings.DATABRICKS_TOKEN,
                settings.DATABRICKS_CHURN_ENDPOINT,
            ),
            _check_databricks_endpoint(
                settings.DATABRICKS_HOST,
                settings.DATABRICKS_TOKEN,
                settings.DATABRICKS_CLV_ENDPOINT,
            ),
        ]
        dependencies["ml_inference"] = (
            "ready"
            if all(status == "ready" for status in endpoint_statuses)
            else "failed"
        )
    else:
        dependencies["ml_inference"] = "unverified"

    tracking_uri = settings.MLFLOW_TRACKING_URI.strip()
    dependencies["mlflow_tracking"] = (
        _check_http_health(tracking_uri, "health") if tracking_uri
        else "failed" if settings.is_production else "not_configured"
    )

    serving_url = settings.MLFLOW_SERVING_URL.strip()
    production = settings.is_production
    if serving_url:
        dependencies["mlflow_serving"] = _check_http_health(serving_url, "ping")
    else:
        dependencies["mlflow_serving"] = "not_configured"

    required_dependencies = ("data_lake",)
    if tracking_uri or production:
        required_dependencies += ("mlflow_tracking",)
    if production and settings.ML_INFERENCE_MODE == "databricks":
        required_dependencies += ("ml_inference",)
    if settings.AI_RATE_LIMIT_ENABLED and (production or settings.REDIS_URL):
        dependencies["redis"] = _check_redis()
        required_dependencies += ("redis",)
    required_checks = [
        "data_lake_backend",
        "ml_inference_mode_configured",
        "upload_limit_configured",
    ]
    if settings.DATA_LAKE_BACKEND == "snowflake":
        required_checks.append("snowflake_credentials_configured")
    if production:
        required_checks.append("mlflow_tracking_configured")
    ready = all(checks[name] for name in required_checks) and all(
        dependencies[name] == "ready" for name in required_dependencies
    )
    if not ready:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "message": "Dependências ou configurações obrigatórias indisponíveis.",
                **checks,
                "dependencies": dependencies,
            },
        )
    return {"status": "ready", "checks": checks, "dependencies": dependencies}
