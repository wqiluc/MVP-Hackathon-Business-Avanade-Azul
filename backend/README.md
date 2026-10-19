# Backend

FastAPI exposes the CRM, upload, dashboard, model and health contracts under
`/api/v1`. Routes validate HTTP input and delegate to application services;
services coordinate the root-level `data/`, `ml/` and `ai/` packages.

## Runtime flow

```text
HTTP routes -> app.services -> data / ml / ai
```

- `app/api/v1/` contains the HTTP endpoints and response schemas.
- `app/services/auth_service.py` validates the existing demo/legacy credentials
  and builds the session; the route maps invalid credentials to HTTP 401.
- `app/services/datalake_service.py` coordinates FileReader, Bronze, Silver,
  Gold, scoring and the configured DuckDB or Snowflake data lake. DuckDB is the
  local backend available for development and tests; Snowflake is the
  implemented data-lake backend intended for the integration environment.
  `DATA_LAKE_BACKEND` selects the backend. Snowflake requires an external
  account and configured credentials; no local Snowflake server is provided.
- `app/services/ml_service.py` coordinates Gold loading, features, training,
  evaluation and tracking through `ml/`.
- `app/services/agent_service.py` adapts API/service inputs to the workflow in
  `ai/agents/`; graph context is provided by `ai/graphrag/`.
- `app/config.py` loads `backend/.env` and keeps the local DuckDB default under
  the repository's `data/processed/`.

The Decision Agent uses deterministic rules and a small static NetworkX graph;
the graph is not a complete GraphRAG implementation and does not use connected
embeddings or vector retrieval. The backend may use OpenAI to personalize
recommendation text after the decision; when OpenAI is disabled, unconfigured,
or unavailable, it uses an explicitly labeled rules fallback. Requests contain
no client identifier or direct personal identifiers.

Client identifiers are pseudonymized with keyed HMAC-SHA256 before persistence.
The key is `JWT_SECRET_KEY`; rotating it requires a coordinated migration.
Pseudonymization is not anonymization.

## Run locally

From the repository root:

```bash
npm start
```

The setup script creates `backend/.venv`, installs backend requirements and
installs the monorepo packages in editable mode. Copy `backend/.env.example`
to `backend/.env` only when local overrides are needed; never commit the local
file. The backend starts with:

```bash
cd backend
.venv/bin/python run.py
```

On Windows, use `.venv\Scripts\python.exe run.py`. The API docs are at
`http://localhost:8000/docs`.

## Tests

Run the backend suite from the repository root:

```bash
cd backend
.venv/bin/python -m pytest -q test
```

For regression runs, set `DUCKDB_PATH` to a temporary database and initialize
the schemas before executing tests that exercise ingestion. The real
`data/processed/azul_datalake.duckdb` must not be used as a test database.

## Known limitations

- Training parameters, metrics and the sklearn model are sent to MLflow by
  `ml/models/mlflow_tracker.py`. The model is registered as
  `AeroShieldChurnModel`, and the `champion` alias identifies the active
  version. Logging explicitly trusts only scikit-learn's tree storage type
  required by the in-process RandomForest; failures are propagated. Tracking
  runs separately from MLflow Serving. See
  `infrastructure/mlflow/README.md` for local startup and validation commands.
- `high_risk_flag` is a rule-derived proxy target, not observed churn.
  `churn_score` is the model score for that proxy target.
- Snowflake connectivity depends on an external account, permissions and
  configuration; it is not provided as a local service.
- Policy context is graph-based and deterministic; external LLM, vector RAG
  and production GraphRAG behavior are not implemented.
