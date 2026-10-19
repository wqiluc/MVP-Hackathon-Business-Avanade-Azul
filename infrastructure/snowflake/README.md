# Snowflake data lake

Snowflake is the required cloud data-lake backend for the CRM integration. DuckDB
remains available for local/offline development. Select the backend explicitly
with `DATA_LAKE_BACKEND=snowflake` or `DATA_LAKE_BACKEND=duckdb`.

The Python service uses the versioned SQL in this directory. The former SQL
under `dados/sql/` describes a separate passenger/loyalty data model and is not
the contract used by this backend.

## Canonical medallion contract

The configured database (default `AZUL_DATA_LAKE`) contains these schemas:

| Layer | Object | Columns |
| --- | --- | --- |
| Bronze | `BRONZE.BRONZE_CLIENTS` | `ID_CLIENTE`, `TIER`, `FREQUENCIA`, `RECENCIA_DIAS`, `GASTO_TOTAL`, `INCIDENTES` |
| Silver | `SILVER.CLEANED_CLIENTS` | `CLIENT_IDENTIFIER`, `TIER`, `FREQUENCY`, `RECENCY_DAYS`, `TOTAL_SPEND`, `FLIGHT_INCIDENTS`, `INGESTED_AT` |
| Gold | `GOLD.CLIENT_FEATURES` | Silver fields except `INGESTED_AT`, plus `AVG_TICKET`, `HIGH_RISK_FLAG`; `CHURN_SCORE` is added after inference |

Snowflake identifiers are case-insensitive; results read by Python are normalized
to lowercase column names.

Before either backend is called, the service replaces source client IDs with
opaque HMAC-SHA256 identifiers using `JWT_SECRET_KEY` and domain separation.
The source IDs are therefore not persisted in Bronze. IDs stay stable while
that key remains unchanged; rotating it requires a coordinated migration of
stored identifiers and their consumers.

Silver preserves the DuckDB rules: the opaque identifier passed from ingestion,
uppercase/trimmed tier, numeric casts, a current ingestion timestamp, and
exclusion of null client IDs. Gold calculates
`ROUND(total_spend / NULLIF(frequency, 0), 2)` and sets high risk when
`flight_incidents >= 2 OR recency_days > 60`. ML is not part of the Gold
transformation.

Bronze ingestion keeps the existing replacement behavior: `write_pandas` uses
`overwrite=True`, not append. Each upload replaces the current Bronze input and
the Silver/Gold output tables are rebuilt from it. This makes the current
pipeline a latest-upload snapshot, not a historical ingestion ledger.

## Provisioning

Use a Snowflake role that can create/use the database and schemas, create tables
and temporary stages, and use the configured warehouse. For the default database, run
`00_create_database.sql` once using SnowSQL or a Snowflake worksheet. If using a
non-default `SNOWFLAKE_DATABASE`, create that database with your administrator
instead of running the default-database script.

Then connect to the configured database and run `01_schemas.sql`. The backend
also applies this idempotent schema script before ingestion. It executes
`02_transform_silver.sql` and `03_transform_gold.sql` as part of every upload.
No stored procedures or external objects are required.

Set these variables in `backend/.env` or the process environment:

```dotenv
DATA_LAKE_BACKEND=snowflake
SNOWFLAKE_ACCOUNT=
SNOWFLAKE_USER=
SNOWFLAKE_PASSWORD=
SNOWFLAKE_DATABASE=AZUL_DATA_LAKE
SNOWFLAKE_WAREHOUSE=COMPUTE_WH
SNOWFLAKE_ROLE=
```

The schemas are fixed to `BRONZE`, `SILVER`, and `GOLD`; there is no single
`SNOWFLAKE_SCHEMA` setting because the medallion layers are separate schemas.
Credentials are not committed. Missing Snowflake credentials do not prevent
the FastAPI application from importing or starting; selecting the Snowflake
backend and attempting ingestion without them returns an explicit configuration
error. Connection failures are not converted to DuckDB success or local scoring.

## Scoring and service flow

The upload route retains its existing HTTP contract:

`UploadService` → `DataLakeService` → selected data-lake backend → Bronze →
Silver → Gold → existing `inference_service.predict_churn` /
`ChurnPredictor` → MLflow Serving → scored Gold.

The same `ChurnPredictor` and `MLFLOW_SERVING_URL` used by DuckDB are reused.
Snowflake does not compute churn locally or import MLflow. Local inference is
rejected for Snowflake even if `MLFLOW_LOCAL_INFERENCE=true`; configure and run
MLflow Serving or ingestion fails explicitly.

## Validation

Run structural SQL/contract tests from `backend/`:

```bash
.venv/bin/python -m pytest -q test/test_snowflake_contract.py
```

The real integration test requires a dedicated, non-production database and a
reachable MLflow Serving endpoint. It replaces the test database's three
pipeline tables with a clearly identified fixture; it never accepts a database
name that does not start with `AEROSHIELD_TEST_`.

```dotenv
SNOWFLAKE_TEST_DATABASE=AEROSHIELD_TEST_MVP
SNOWFLAKE_INTEGRATION_TESTS=1
MLFLOW_SERVING_URL=http://localhost:5001/invocations
```

```bash
cd backend
.venv/bin/python -m pytest -q test/test_snowflake_contract.py \
  -k real_snowflake_pipeline
```

That test creates the explicitly named test database if needed, uploads a
fixture through `DataLakeService`, verifies Bronze/Silver/Gold, compares Gold
business columns with the DuckDB transformations, and confirms that real
MLflow Serving produced persisted scores. Without credentials, the dedicated
test is skipped and the integration is **not** considered end-to-end validated.
