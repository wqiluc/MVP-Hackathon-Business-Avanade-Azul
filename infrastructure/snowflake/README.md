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

Each successful upload replaces the entire Bronze/Silver/Gold snapshot, not
an append or a historical ledger. `write_pandas` writes only to session-local
candidate tables with `overwrite=False` and `auto_create_table=False`.
The existing transformation SQL is applied to those candidates, never directly
to the active tables during upload. Scoring also runs against the candidate.

## Atomic publication

All candidate layers and persisted scores are validated before publication.
Schema/bootstrap DDL, temporary-stage/COPY operations and scoring finish before
the explicit publication transaction begins. This matters because Snowflake DDL
implicitly commits: BEGIN around the former CREATE OR REPLACE pipeline would
**not** provide rollback.

The backend provisions `GOLD.SNAPSHOT_PUBLICATION` using one
`CREATE TABLE IF NOT EXISTS ... AS SELECT` with exactly one control row.
Within a DML-only transaction it:

1. Updates that row with the execution ID and publication timestamp, acquiring
   a database publication lock held until commit/rollback.
2. Deletes and inserts the validated candidate rows into each active table,
   always in Bronze/Silver/Gold order.
3. Commits all three layers and the metadata together.

Other application writers use the same control row. Unlike a process lock or
an expiring Redis lease, the lock participates in the publication transaction.
Candidate uploads may prepare concurrently; publication is serialized.
`LOCK_TIMEOUT=5` bounds lock waits. Timeout or any publication error fails the
request with the existing safe server-error handling and no automatic retry.
Pre-publication errors only discard candidates; publication errors roll back.
Temporary candidate tables are session-local and disappear on connection close.
No historical backup is retained after a successful commit.

The CRM reads only the active Gold table in one SELECT. Snowflake's READ COMMITTED
isolation prevents dirty reads, but does not pin multiple SELECT statements or
separate API requests to the same version. Different sessions can briefly see
different **complete** committed versions under the account's consistency mode.
No account-level consistency settings are changed here.

Network loss during COMMIT can leave the commit outcome unknown to the caller.
Inspect the active execution ID after reconnection instead of assuming rollback.
Do not run external DDL writers against active/control tables during publication;
all application snapshot writers must use this protocol.

## Provisioning

Use a Snowflake role that can create/use the database and schemas, create tables
and temporary stages, and use the configured warehouse. For the default database, run
`00_create_database.sql` once using SnowSQL or a Snowflake worksheet. If using a
non-default `SNOWFLAKE_DATABASE`, create that database with your administrator
instead of running the default-database script.

Then connect to the configured database and run `01_schemas.sql`. The backend
also applies this idempotent schema script before ingestion. It executes
`02_transform_silver.sql` and `03_transform_gold.sql` against temporary candidate
names as part of every upload. The role also needs SELECT/INSERT/DELETE on active
tables and SELECT/UPDATE on `GOLD.SNAPSHOT_PUBLICATION`. No stored procedures,
Redis data locks or additional services are required.

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
Snowflake does not compute churn locally or import MLflow. Without Tracking or
a registered model, scores remain null. When model scoring is requested,
MLflow Serving must be configured and available; the legacy
`MLFLOW_LOCAL_INFERENCE` flag never substitutes heuristic model scores.

## Validation

Run structural SQL/contract tests from `backend/`:

```bash
.venv/bin/python -m pytest -q test/test_snowflake_contract.py
```

`test/test_snowflake_publication.py` additionally simulates the connector using
a local SQL engine. It checks candidate-only writes, DML-only publication,
failure injection before/inside publication, and previous-snapshot retention.
These tests do not validate real Snowflake concurrency, permissions, connection
cleanup or isolation. Real-server validation remains a separate requirement.

The real integration test requires a dedicated, non-production database and a
reachable MLflow Tracking/Serving with `MLFLOW_MODEL_NAME` set to an authorized
model whose `champion` alias is ready. It replaces the test database's three
pipeline tables with a clearly identified fixture; it never accepts a database
name other than `CRM_TEST_E2E`. This database must be explicitly reserved for
tests without real data; its name alone does not guarantee isolation.

```dotenv
SNOWFLAKE_TEST_DATABASE=CRM_TEST_E2E
SNOWFLAKE_INTEGRATION_TESTS=1
MLFLOW_TRACKING_URI=http://localhost:5000
# Set MLFLOW_MODEL_NAME to the authorized Registry model name.
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
The bootstrap always issues `CREATE DATABASE IF NOT EXISTS`, including for an
existing destination. Verify the required privilege/authorization before
enabling it; the test does not remove its database, tables or fixture afterward.
