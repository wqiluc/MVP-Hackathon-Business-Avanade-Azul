# CRM de Alto Valor API

FastAPI exposes the CRM, upload, dashboard, model and health contracts under
`/api/v1`. Routes validate HTTP input and delegate to application services;
services coordinate the root-level `data/`, `ml/` and `ai/` packages.

For the endpoint-by-endpoint HTTP contract, authentication requirements and
response behavior, see the [API reference](../docs/api/README.md).

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
The legacy HMAC domain is intentionally stable: it is a cryptographic
compatibility identifier, not application branding. Renaming it would change
persisted client identifiers and requires a separate migration.

## Production configuration safeguards

Set `ENVIRONMENT=production` in the process environment before starting the API.
In this mode, local dotenv files are not loaded. Inject credentials through the
deployment environment; never copy development credentials into production.
Unknown environment names fail startup instead of bypassing production checks.

- `JWT_SECRET_KEY` must be persistent, randomly generated, at least 32 characters,
  and not an example or low-diversity value. Diversity checks reject obvious weak
  inputs but cannot prove entropy; use a cryptographically secure generator.
- `ADMIN_EMAIL` and `ADMIN_PASSWORD` are required. The password must have at least
  16 characters with adequate diversity and cannot be an example/default.
- Leave both `DEMO_EMAIL` and `DEMO_PASSWORD` empty in production. Startup rejects
  demo configuration, and login independently refuses demo accounts there.
  Development/test still allow the existing configured demo login.
- CORS origins must be explicit HTTP(S) origins without wildcards or credentials.
- With AI admission enabled, production requires Redis. Readiness probes it using
  the same bounded client as admission control; liveness never probes dependencies.
  Redis failure does not enable in-memory admission in production.

The frontend uses one HTTP client for login and CRM calls, with a 60-second
timeout (120 seconds for upload), cancellation support, no automatic retries,
and safe status-specific errors. A 429 retains `Retry-After` as seconds (numeric
or HTTP-date) and shows the wait to the user. Aborting a client request does not
roll back processing already started by the server; verify an upload's result
before resubmitting it.

Session persistence is fail-closed: blocked or invalid session storage rejects
login rather than keeping an unpersisted token. Expired/invalid sessions are
cleared; the authentication context follows expiry and rechecks on window focus.

`MAX_UPLOAD_BYTES` limits the file content, not the full multipart body. A future
reverse proxy must account for multipart overhead and enforce its own request
limit. The authenticated upload, canonical CSV contract, pseudonymization and
temporary-file cleanup remain unchanged.

Frontend service regression tests use Node's built-in test runner and the
existing TypeScript compiler: `cd frontend && npm test`. They are unit tests,
not browser E2E or real-provider smoke tests.

## AI request budgets and provider retries

The application limits authenticated recommendation requests **before** client
lookup, the Decision Agent and any OpenAI call. The same dependency also protects
the analysis endpoints, which currently run the deterministic workflow without
OpenAI. Canonical and legacy aliases share the same budgets; changing a client
ID, endpoint alias, IP or JWT token does not reset an authenticated user's budget.
Read-only client/dashboard requests and upload are unchanged.

| Setting | Default | Purpose |
|---|---|---|
| `AI_RATE_LIMIT_ENABLED` | `true` | Enable application admission control |
| `AI_RATE_LIMIT_REQUESTS` | `10` | Requests per JWT `sub` in one window |
| `AI_RATE_LIMIT_WINDOW_SECONDS` | `60` | Window duration, starting on first admitted request |
| `AI_RATE_LIMIT_IP_REQUESTS` | `100` | Secondary shared IP barrier, allowing multiple users behind NAT |
| `AI_OPENAI_MAX_RETRIES` | `2` | Additional provider attempts; validated range 0–2 |
| `REDIS_URL` | empty | Shared Redis counter store; use `rediss://` when TLS is required |

These are **our application's budgets**, not official OpenAI/free-tier limits.
Without a usable JWT subject, the peer IP uses the stricter user-sized budget.
Keys contain keyed hashes, not raw subjects or IPs. All recommendation requests
count, including requests served by rules or returning 404. Blocked requests
do not increment counters or invoke the workflow.

Development without `REDIS_URL` uses an expiring, thread-safe in-memory store,
valid for **one process only**. Set `AI_RATE_LIMIT_ENABLED=false` explicitly to
disable admission control locally. Tests disable it in a per-test fixture unless
they specifically exercise limits, avoiding cross-test state.

With the limiter enabled, production **requires `REDIS_URL`** and never falls
back to memory. The repository did not previously provision Redis or declare a
Redis client: this implementation adds the Python client, not another server or
deployment stack. Configure an existing/reachable Redis service separately.
Use an isolated Redis database with authentication, restricted network access,
and a capacity/eviction policy that does not evict active rate-limit keys.
The connection has bounded connect/read timeouts and no automatic command
retries, avoiding duplicate increments after ambiguous transport failures.
Both user and IP counters are checked/incremented atomically by Lua, with TTLs
set on first use and shared by all backend workers.

The limiter reads only the ASGI peer address, not arbitrary `X-Forwarded-For`
headers. Behind a reverse proxy, configure Uvicorn's trusted proxy IP allowlist
for the actual proxy addresses; never trust forwarded headers from all clients.
Otherwise the proxy/NAT address shares the secondary budget by design.

An exhausted budget returns HTTP **429**, `Retry-After` in integer seconds
(rounded up from remaining TTL), and the existing API error envelope:

```json
{
  "success": false,
  "error": "AI_RATE_LIMIT_EXCEEDED",
  "message": "Muitas solicitações de IA. Tente novamente em instantes.",
  "detail": {
    "code": "AI_RATE_LIMIT_EXCEEDED",
    "message": "Muitas solicitações de IA. Tente novamente em instantes."
  },
  "status_code": 429,
  "path": "/api/v1/clientes/example/recomendacao"
}
```

`Retry-After` is exposed through CORS. A Redis/configuration failure returns
**503 / `AI_RATE_LIMIT_UNAVAILABLE`** and logs a safe error rather than admitting
unmetered work. Production startup rejects a missing Redis URL when enabled;
runtime requests fail closed if Redis is unreachable.

OpenAI `RateLimitError` is a separate mechanism. The SDK's internal retries stay
disabled. Only temporary provider rate limits are retried, honoring numeric or
HTTP-date `Retry-After` and exponential backoff. Quota/billing, transport errors
and invalid structured outputs are not retried. A provider delay exceeding
`OPENAI_TIMEOUT_SECONDS` immediately selects fallback instead of retrying early
or occupying a worker for an unbounded delay.

A request generates at most `1 + AI_OPENAI_MAX_RETRIES` provider calls (maximum
three). Provider failures retain HTTP 200 with an explicitly labeled
`llm-indisponivel` rules recommendation; disabling/unconfiguring the provider
retains the normal `regras` origin. Neither changes `high_risk_flag`, null scores,
GraphRAG, the Decision Agent, or policy/eligibility notices.

The fixed windows are not a global monthly quota or concurrency limiter: traffic
can burst across a window boundary. Monitor usage and configure budgets alongside
provider-side spending limits. The normal suite tests Lua using `fakeredis[lua]`.
The opt-in tests below instead connect to a real local Redis server. Local
validation does not certify connectivity or failover in another deployment.

### Disposable real Redis smoke test (macOS)

This student MVP needs no Redis Cloud account, subscription or paid service.
Use Docker CLI with a local runtime such as Colima. Install tools separately
with the user's permission; no Docker Desktop, native Redis installation,
Kubernetes, Compose changes or permanent Redis infrastructure is required.

From the repository root, after starting the local Docker runtime:

```bash
docker info
docker run --rm hello-world
docker run -d --name crm-redis-smoke-test \
  -p 127.0.0.1:6379:6379 redis:7-alpine
docker exec crm-redis-smoke-test redis-cli ping
docker exec crm-redis-smoke-test redis-cli INFO server
```

Expected: `PONG`, Redis `7.x`, and a port published only on loopback.
Use this only for a disposable smoke-test container; do not remove an existing
unrelated container or reuse a Redis instance containing user data.

Run the following in a subshell so temporary settings do not persist. These
tests bypass the normal suite's disabled-limiter fixture, never use fakeredis,
and guard OpenAI against external calls. The available test uses the real
60-second window, so it takes approximately one minute:

```bash
(
  cd backend
  export REDIS_URL=redis://127.0.0.1:6379/0
  export AI_RATE_LIMIT_ENABLED=true AI_RATE_LIMIT_REQUESTS=2
  export AI_RATE_LIMIT_WINDOW_SECONDS=60 AI_RATE_LIMIT_IP_REQUESTS=5
  export DUCKDB_PATH=/tmp/crm-redis-real-validation.duckdb
  export DATA_LAKE_BACKEND=duckdb ENVIRONMENT=development
  export LLM_PROVIDER=disabled OPENAI_API_KEY=''
  CRM_REAL_REDIS_SMOKE=available .venv/bin/python -m pytest -q \
    test/test_ai_rate_limit_real_redis.py --disable-warnings
  docker stop crm-redis-smoke-test
  CRM_REAL_REDIS_SMOKE=unavailable .venv/bin/python -m pytest -q \
    test/test_ai_rate_limit_real_redis.py --disable-warnings
)
docker rm -f crm-redis-smoke-test
docker ps -a --filter 'name=^/crm-redis-smoke-test$'
```

Each phase should report one passed test and one intentionally skipped test.
The available phase verifies application connectivity, atomic increments under
concurrency, TTL, user/IP budgets, 429/Retry-After, blocked CRM/OpenAI access,
real expiry and readmission. The unavailable phase verifies request-time
production 503 without memory fallback; it isolates admission control from
unrelated Snowflake/MLflow production startup requirements.

Always remove only the disposable smoke-test container after testing, including
on failure. Colima may remain installed. Without `CRM_REAL_REDIS_SMOKE`, both
real-server tests are skipped and the normal suite needs no running Redis.

Validated locally with Colima 0.10.3, Docker Engine 29.5.2 and Redis 7.4.11
(`redis:7-alpine`) on macOS arm64. Both real-server phases passed.

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

For local development, select `DATA_LAKE_BACKEND=duckdb`, set
`LLM_PROVIDER=disabled`, leave `REDIS_URL`, `MLFLOW_TRACKING_URI`,
`MLFLOW_MODEL_NAME` and `MLFLOW_SERVING_URL` empty, and configure your own
`DEMO_EMAIL`/`DEMO_PASSWORD`. No default backend login is provided. Use a
persistent random `JWT_SECRET_KEY` to keep HMAC identifiers stable across
restarts. An empty development key is ephemeral, not suitable for retained data.

MLflow is optional locally. Without Tracking or a model name, `GET /modelo`
returns `aguardando-configuracao` with null metrics; uploads without Tracking
or a registered model keep null scores with `awaiting_model_registration`.
No heuristic substitutes a model score, including with the legacy
`MLFLOW_LOCAL_INFERENCE` flag. Training is an explicit admin operation requiring
Tracking and `MLFLOW_MODEL_NAME`; it is never performed at startup.
Configured dependencies fail explicitly if unavailable; only unconfigured
MLflow is omitted from local readiness requirements. Production still requires
remote Tracking, an explicit model name and Serving.

## Tests

Run the backend suite from the repository root:

```bash
cd backend
SNOWFLAKE_INTEGRATION_TESTS=0 MLFLOW_INTEGRATION_TESTS=0 \
  DATA_LAKE_BACKEND=duckdb MLFLOW_TRACKING_URI= MLFLOW_SERVING_URL= \
  LLM_PROVIDER=disabled OPENAI_API_KEY= \
  .venv/bin/python -m pytest -q -p no:cacheprovider
```

For regression runs, set `DUCKDB_PATH` to a temporary database and initialize
the schemas before executing tests that exercise ingestion. The real
`data/processed/azul_datalake.duckdb` must not be used as a test database.

## Upload snapshot publication and recovery

Uploads replace the entire current client base; they do not append records.
The canonical header remains, in this order:

```csv
id_cliente,tier,frequencia,recencia_dias,gasto_total,incidentes
```

Existing header case/whitespace normalization is retained, but extra, missing,
duplicate or reordered canonical columns are rejected. The existing legacy
adapter remains separate; `CUSTOMER_ID` is not the canonical contract.
Every dataset is limited to 100,000 rows as well as `MAX_UPLOAD_BYTES` (10 MiB
by default). Canonical IDs must be nonempty and unique after trimming, without
control characters. Tiers are Basico/Básico, Topazio/Topázio, Safira or Diamante
(case-insensitive). Counts/recency must be integers from 0 to 2,147,483,647;
spend must be finite and nonnegative. Source IDs are still HMAC-pseudonymized
before persistence. Numeric-looking text IDs retain leading zeros.

- **Current:** the last committed Bronze/Silver/Gold tables.
- **Candidate:** uncommitted DuckDB changes, or session-local Snowflake staging
  tables. Candidate layers and persisted scores are checked before publication.
- **Published:** one commit makes all three layers and the execution ID visible.
  `gold.snapshot_publication` records the active execution ID and publication
  time, not historical client data. Existing snapshots receive this metadata on
  their next successful upload.
- **Failed:** DuckDB rolls back the transaction; Snowflake discards its staging
  session or rolls back publication DML. The previous committed base stays active.
  A first failed upload does not publish a candidate base.

DuckDB uses native transactional DDL, including the existing transformations.
Readers keep seeing the previous committed Gold during processing. A nonblocking
writer lock keyed by database path rejects a second upload in the same process
with HTTP 409. Run local DuckDB with one backend process; this is **not** a
distributed lock and DuckDB does not support independent read/write application
processes sharing this database. Transactions still protect against partial
publication if another connection encounters a write conflict.

Snowflake stages the candidate in temporary tables and serializes publication
using an UPDATE of a singleton database control row. Only DML and reads occur
between BEGIN and COMMIT; no table swaps or CREATE OR REPLACE of active tables.
See [Snowflake publication details](../infrastructure/snowflake/README.md).
The last successfully committed publication wins, not necessarily the upload
that arrived last. A publication lock wait over five seconds fails the request;
there is no automatic retry or Redis lease.

Ingestion runs in a worker thread so the async API event loop remains available.
One execution ID follows upload processing, publication/rollback and duration
logs; filenames, original IDs, CSV contents and credentials are not logged.
Health/liveness remains dependency-free. Readiness checks the selected data
backend and required Redis. Locally, Tracking and Serving are optional when
unconfigured; configured endpoints are checked. Production still requires both.
Optional OpenAI is not a readiness dependency.

Recovery here means rollback **before successful publication**, not keeping
multiple historical snapshots. After an ambiguous network failure during COMMIT,
do not assume the previous version won: inspect `snapshot_publication` after
connectivity returns. The outcome may be the complete old or complete new base,
not a partially committed base. This change does not provide backups, restore
history, upload cancellation, or cross-request snapshot pinning. Each CRM read
sees a committed Gold; separate API requests may straddle a publication.

Focused tests:

```bash
cd backend
.venv/bin/python -m pytest -q -p no:cacheprovider \
  test/test_file_reader.py test/test_snapshot_publication.py \
  test/test_snowflake_publication.py test/test_e2e_local_pipeline.py \
  test/test_health_readiness.py
```

Snapshot concurrency/rollback tests exercise real disposable DuckDB databases.
Snowflake publication tests simulate the connector and SQL dialect locally;
they verify orchestration and SQL boundaries, **not** real Snowflake locking,
permissions, isolation or network behavior. The separately gated real Snowflake
integration remains opt-in and requires a dedicated test database.

## Known limitations

- Training parameters, metrics and the sklearn model are sent to MLflow by
  `ml/models/mlflow_tracker.py`. The exact registered model name is supplied by
  `MLFLOW_MODEL_NAME`, and the `champion` alias identifies the active
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
