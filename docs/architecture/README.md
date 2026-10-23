# Arquitetura do CRM de Alto Valor

O repositório `crm-alto-valor` é um monorepo modular. FastAPI é o orquestrador
do backend: as rotas validam contratos HTTP e delegam coordenação aos serviços
de aplicação. MLflow Tracking e MLflow Serving são processos/serviços
separados; Snowflake é uma plataforma externa. Esses serviços não executam no
processo FastAPI.

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
  do score. Layers candidatos e scores são validados antes da publicação.
  DuckDB publica camadas e identificador da execução em uma transação;
  Snowflake serializa a publicação com uma linha de controle e DML entre
  `BEGIN` e `COMMIT`. Falhas antes do commit preservam o snapshot ativo anterior.
  Consulte [dados e publicação](../data/README.md) para limites de concorrência
  e recuperação.
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

## Roteamento do Data Lake

`UploadService` lê o arquivo e delega a `DataLakeService`.
`DataLakeService` seleciona `DuckDBDataLake` para execução local/offline ou
`SnowflakeDataLake` quando `DATA_LAKE_BACKEND=snowflake`. Ambos implementam o
contrato de negócio medallion; DDL e transformações Snowflake são versionados
em `infrastructure/snowflake/`.

O fluxo de processamento é Bronze → Silver → Gold, seguido por
`inference_service.predict_churn` / `ChurnPredictor` → MLflow Serving. O score
resultante é gravado em Gold. MLflow permanece fora dos adapters de dados, e
falhas de Snowflake são explícitas: não há troca silenciosa para DuckDB ou
inferência local.

Bronze Snowflake preserva a semântica de substituição por dataset enviado.
DuckDB permanece como backend local; os adapters são conexões independentes.
O teste de integração Snowflake exige conta de teste dedicada e MLflow Serving
disponível, e não é substituído pelos testes locais com mocks.

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
