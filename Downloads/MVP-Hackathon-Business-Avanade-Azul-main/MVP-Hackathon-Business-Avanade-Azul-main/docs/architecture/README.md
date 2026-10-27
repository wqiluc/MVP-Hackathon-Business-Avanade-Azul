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
  do score ou `NULL` com status de features ausentes. Layers candidatos e scores
  são validados antes da publicação.
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
  evidências. OpenAI ou Gemini podem personalizar o texto por uma camada comum
  no backend. Se o provider estiver desabilitado ou sem configuração, o serviço
  usa regras; uma segunda opção só é tentada se `LLM_FALLBACK_PROVIDER` estiver
  explicitamente configurado. Falhas são identificadas na origem da recomendação.

`infrastructure/snowflake/` mantém o SQL canônico do Data Lake e
`infrastructure/mlflow/` documenta a configuração legada de Tracking/Registry
e Serving. Os modelos empacotados de churn e CLV têm provider próprio (MLflow
local ou Databricks Serving), contratos de 52 features e não são parte do
treinador legado de cinco features. `high_risk_flag` é uma proxy por regra, não
churn observado; `churn_score` legado é o score do modelo para esse target.
O grafo de contexto é estático e ilustrativo: não há recuperação vetorial,
embeddings conectados ou ChromaDB.

## Roteamento do Data Lake

`UploadService` lê o arquivo e delega a `DataLakeService`.
`DataLakeService` seleciona `DuckDBDataLake` para execução local/offline ou
`SnowflakeDataLake` quando `DATA_LAKE_BACKEND=snowflake`. Ambos implementam o
contrato de negócio medallion; DDL e transformações Snowflake são versionados
em `infrastructure/snowflake/`.

O fluxo de processamento é Bronze → Silver → Gold, seguido pelos serviços
`ChurnService` e `ClvService` quando todas as features dos contratos reais
estão presentes. O provider é selecionado por `ML_INFERENCE_MODE` (`local` ou
`databricks`); os resultados são gravados em Gold com metadados do modelo.
Como a ingestão atual só fornece seis campos, Gold publica scores nulos e
`awaiting_model_features`, sem inferir as demais features. Falhas do provider
configurado são explícitas e não acionam fallback para o scorer legado ou
heurísticas.

Bronze Snowflake preserva a semântica de substituição por dataset enviado.
DuckDB permanece como backend local; os adapters são conexões independentes.
O teste de integração Snowflake exige conta de teste dedicada; testes com
providers externos usam mocks e não comprovam disponibilidade Databricks.

Antes de qualquer persistência, o serviço substitui IDs da origem por
pseudônimos HMAC-SHA256 vinculados a `JWT_SECRET_KEY`. A exposição monetária
`value_at_risk` do workflow é uma heurística (`total_spend × 1.30 × churn_score`),
não uma previsão financeira calibrada.

## Configuração de produção (fail-closed)

Com `ENVIRONMENT=production`, o startup do backend aborta se faltar qualquer item:
`DATA_LAKE_BACKEND=snowflake`; `SNOWFLAKE_ACCOUNT/USER/PASSWORD/DATABASE/WAREHOUSE`;
`MLFLOW_TRACKING_URI` remoto e `MLFLOW_MODEL_NAME` para o fluxo de treino legado;
provider válido dos modelos empacotados (`ML_INFERENCE_MODE=local` com ambos os
diretórios de modelo, ou `databricks` com host, token e endpoints de churn/CLV);
além de `JWT_SECRET_KEY`, `ADMIN_EMAIL` e `ADMIN_PASSWORD`.
Mensagens de erro nunca incluem valores de segredos. Desenvolvimento e testes mantêm os defaults (DuckDB/local).

Importante: a validação de startup verifica configuração; readiness também
consulta Snowflake, MLflow Tracking e, no modo Databricks, os dois endpoints de
serving. Isso não substitui testes reais de inferência com credenciais e
features válidas.
