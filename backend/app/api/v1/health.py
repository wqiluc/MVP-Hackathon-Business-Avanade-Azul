from urllib.parse import urlparse, urlunparse

import requests
from fastapi import APIRouter, HTTPException, status

from app.config import settings

router = APIRouter()
_DEPENDENCY_TIMEOUT_SECONDS = 2


@router.get("/")
def check_health():
    return {
        "status": "online",
        "service": "AeroShield AI BFA",
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


@router.get("/ready")
def readiness():
    checks = {
        "data_lake_backend": settings.DATA_LAKE_BACKEND in {"duckdb", "snowflake"},
        "mlflow_tracking_configured": bool(settings.MLFLOW_TRACKING_URI.strip()),
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

    tracking_uri = settings.MLFLOW_TRACKING_URI.strip()
    dependencies["mlflow_tracking"] = (
        _check_http_health(tracking_uri, "health") if tracking_uri else "failed"
    )

    serving_url = settings.MLFLOW_SERVING_URL.strip()
    production = settings.ENVIRONMENT.lower() == "production"
    if serving_url:
        dependencies["mlflow_serving"] = _check_http_health(serving_url, "ping")
    else:
        dependencies["mlflow_serving"] = "failed" if production else "not_configured"

    required_dependencies = ("data_lake", "mlflow_tracking")
    if serving_url or production:
        required_dependencies += ("mlflow_serving",)
    ready = all(checks.values()) and all(
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
