# Arquitetura atual

O repositório é um monorepo modular. Os componentes de aplicação/backend
integrados executam no processo da aplicação FastAPI. MLflow Tracking e MLflow
Serving são processos/serviços separados, e Snowflake é uma plataforma externa;
esses serviços não executam no processo FastAPI.

```text
Frontend (React/Vite)
  -> backend/app/api/v1 (HTTP, autenticação, schemas)
  -> backend/app/services (coordenação e contratos de aplicação)
      -> data (FileReader, Bronze, Silver, Gold, DuckDB Adapter)
      -> ml (features, training, evaluation, inference, MLflow tracker)
      -> ai (LangGraph workflow, NetworkX context graph)
  -> DuckDB local ou integração Snowflake configurada
```

## Fluxos

- **Upload:** `UploadService` salva arquivo temporário e delega ao
  `DataLakeService`; FileReader → Bronze → Silver → Gold → scoring → persistência
  do score. O serviço fecha a conexão depois da contagem e resposta.
- **Treinamento:** `ml_service` lê Gold → valida linhas → `ml.features` prepara
  X/y → `ml.training` executa split e RandomForest → `ml.evaluation` calcula
  métricas → `ml.models` registra no MLflow → serviço devolve o contrato da API.
- **Análise/recomendação:** a API chama serviços; `ai/agents` calcula exposição,
  recupera contexto por `ai/graphrag` e o Decision Agent determina a ação e as
  evidências. OpenAI pode personalizar a recomendação pelo backend; se estiver
  desabilitada, sem chave ou indisponível, o serviço usa regras e marca
  explicitamente a origem.

`infrastructure/snowflake/` mantém o SQL canônico do Data Lake e
`infrastructure/mlflow/` documenta a configuração de Tracking/Registry e o
procedimento separado de MLflow Serving. `high_risk_flag` é uma proxy por
regra, não churn observado; `churn_score` é o score do modelo para esse target.
O grafo de contexto é estático e ilustrativo: não há recuperação vetorial,
embeddings conectados ou ChromaDB.

## Data lake backend routing

`UploadService` lê o arquivo e delega a `DataLakeService`.
`DataLakeService` selects `DuckDBDataLake` for local/offline runs or
`SnowflakeDataLake` when `DATA_LAKE_BACKEND=snowflake`. Both implement the
same medallion business contract; Snowflake DDL and transformations are
versioned in `infrastructure/snowflake/`.

The processing flow is Bronze → Silver → Gold, followed by the existing
`inference_service.predict_churn` / `ChurnPredictor` → MLflow Serving call.
The resulting score is written back to Gold. MLflow remains outside the
data-layer adapters, and Snowflake failures are explicit rather than falling
back silently to DuckDB or local inference.

Snowflake Bronze preserves the existing overwrite behavior for each uploaded
dataset. DuckDB remains available as the local development backend; the two
backends are separate connections and can be compared with the real Snowflake
integration test when a dedicated test account and MLflow Serving are available.

Antes de qualquer persistência, o serviço substitui IDs da origem por
pseudônimos HMAC-SHA256 vinculados a `JWT_SECRET_KEY`. A exposição monetária
`value_at_risk` do workflow é uma heurística (`total_spend × 1.30 × churn_score`),
não uma previsão financeira calibrada.

## Configuração de produção (fail-closed)

Com `ENVIRONMENT=production`, o startup do backend aborta se faltar qualquer item:
`DATA_LAKE_BACKEND=snowflake`; `SNOWFLAKE_ACCOUNT/USER/PASSWORD/DATABASE/WAREHOUSE`;
`MLFLOW_TRACKING_URI` remoto (não localhost/arquivo); `MLFLOW_MODEL_NAME` fornecido pelo ambiente;
`MLFLOW_SERVING_URL` http(s) não vazia;
`MLFLOW_LOCAL_INFERENCE=false`; além de `JWT_SECRET_KEY`, `ADMIN_EMAIL` e `ADMIN_PASSWORD`.
Mensagens de erro nunca incluem valores de segredos. Desenvolvimento e testes mantêm os defaults (DuckDB/local).

Importante: essa validação é apenas de configuração e não conecta a serviços externos.
A disponibilidade real de Snowflake e MLflow deve ser confirmada pelos checks de health/readiness
do deploy; a conectividade real permanece não validada sem credenciais externas.
