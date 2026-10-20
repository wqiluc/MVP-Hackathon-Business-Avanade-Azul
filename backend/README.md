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
