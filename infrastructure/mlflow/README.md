# MLflow local infrastructure

The local hackathon setup runs a real MLflow Tracking Server with a SQLite
backend store and a local, server-proxied artifact directory. No Docker,
PostgreSQL, object storage, or edits to `backend/mlflow.db` are required.

## Start Tracking

`npm start` starts this service automatically when `MLFLOW_TRACKING_URI` points
to a local HTTP endpoint (the default is `http://localhost:5000`). The metadata
database and artifacts are stored under the ignored path
`infrastructure/mlflow/data/`.

To start Tracking separately from the application:

```bash
mkdir -p infrastructure/mlflow/data/artifacts
backend/.venv/bin/python -m mlflow server \
  --backend-store-uri sqlite:///infrastructure/mlflow/data/tracking.db \
  --artifacts-destination file://$PWD/infrastructure/mlflow/data/artifacts \
  --host 127.0.0.1 \
  --port 5000 \
  --workers 1
```

The Tracking API and UI are available at `http://localhost:5000`. Set
`MLFLOW_TRACKING_URI=http://localhost:5000` for the backend. The server persists
experiments, runs, and Registry metadata in `tracking.db`; model artifacts are
stored below `infrastructure/mlflow/data/artifacts/` and accessed through the
Tracking Server's artifact proxy.

The API's `/api/v1/health/live` endpoint is process-only. `/api/v1/health/ready`
checks the configured data lake (a local `SELECT 1` for DuckDB or a bounded,
read-only `SELECT 1` for Snowflake) and Tracking Server; Tracking uses MLflow's
`/health` endpoint with a short timeout. If Serving is configured, readiness
also checks its `/ping` endpoint (derived from the configured
`MLFLOW_SERVING_URL`, normally `/invocations`). Local development may omit
Serving; production requires it. Readiness does not train models or call the
LLM. Probe responses expose dependency states, not connection errors or
credentials.

## Train, register, and activate

Start the API, ingest data into Gold, then call the existing authenticated
`POST /api/v1/modelo/train` endpoint. A successful training run logs parameters,
metrics, and the sklearn model, registers a new `AeroShieldChurnModel` version,
and sets the `champion` alias to that version. The existing authenticated
`GET /api/v1/modelo` endpoint reads that alias from the Registry.

## Start Serving

Serving is a separate process from Tracking. After a model version has been
registered, start the model currently referenced by the `champion` alias:

```bash
PATH="$PWD/backend/.venv/bin:$PATH" \
MLFLOW_TRACKING_URI=http://localhost:5000 \
  backend/.venv/bin/python -m mlflow models serve \
  --model-uri models:/AeroShieldChurnModel@champion \
  --host 127.0.0.1 \
  --port 5001 \
  --env-manager local
```

Set `MLFLOW_SERVING_URL=http://localhost:5001/invocations` in
`backend/.env`. The predictor sends `dataframe_split` requests and propagates
Serving failures; it does not silently replace an unavailable model with
rule-based scores. Rule-based inference is available only when
`MLFLOW_LOCAL_INFERENCE=true` is explicitly set for local development or tests.

Do not delete or reuse `backend/mlflow.db`; it is a pre-existing project
artifact, separate from this local Tracking Server's storage.

## Integration tests

The isolated integration test starts temporary Tracking and Serving processes
and uses a temporary SQLite database and artifact directory:

```bash
cd backend
MLFLOW_INTEGRATION_TESTS=1 .venv/bin/python -m pytest -q test/test_mlflow_integration.py
```
