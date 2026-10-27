# Databricks Model Serving — Setup e Smoke Test

Status: **BLOCKED_EXTERNAL**. Nenhum workspace, endpoint ou credencial Databricks
estava disponível ao preparar este documento. Nada aqui foi validado contra um
endpoint real; os testes automatizados usam HTTP mockado.

## Como a aplicação consome o Databricks

Arquitetura: `React → FastAPI → Databricks`. O frontend nunca conhece host, token
ou endpoints.

- Ativação: `ML_INFERENCE_MODE=databricks` (padrão: `local`). Não há fallback
  automático entre providers.
- Implementação: `DatabricksServingInferenceProvider`
  (`backend/app/services/ml/inference_provider.py`).
- Request: `POST {DATABRICKS_HOST}/api/2.0/serving-endpoints/{endpoint}/invocations`
  com `Authorization: Bearer <token>` e corpo
  `{"dataframe_split": {"columns": [52 features na ordem do contrato], "data": [...]}}`.
  O formato `dataframe_split` é um dos formatos aceitos por endpoints de pyfunc
  do Model Serving; confirme no smoke test.
- Response esperada: `{"predictions": ...}`.
  - Churn: matriz `n × 2` de probabilidades (`predict_proba`); a ordem das classes
    vem de `ML_CHURN_CLASS_ORDER` (padrão `0,1`); o score é a coluna da classe `1`.
  - CLV: um valor numérico finito por linha.
- Timeout: `ML_INFERENCE_TIMEOUT_SECONDS` (padrão 15 s). **Não há retry** (chamada
  única), adequado ao Render e sem espera extra para erros permanentes.
- Erros: 401, 403, 404, 408, 429, 5xx, timeout, falha de conexão, JSON inválido e
  resposta sem `predictions` viram `ModelInferenceError` sem expor token nem
  detalhes do endpoint. O upload nunca falha por isso:
  `scoring_status` = `scored` (ambos), `partial` (um) ou `unavailable` (nenhum).
  Nunca é gerado score ou CLV substituto (nem `0`).
- As 52 features vêm exclusivamente do `FeatureBuilder` estrito (sem aliases nem
  defaults). Identificadores, CPF, target e colunas de treino não são enviados.

## Modelos (não substituir)

| Modelo | Registro | Versão | Endpoint |
|---|---|---|---|
| Churn | `workspace.default.churn_gb2` | 1 | `<a definir pelo responsável>` |
| CLV | `workspace.default.clv_gb` | 3 | `<a definir pelo responsável>` |

O `CLVtest.ipynb` (XGBoost/Snowflake) é outro modelo e **não** substitui o CLV v3.

## Configuração no Render (valores reais somente como secrets)

```text
ML_INFERENCE_MODE=databricks
DATABRICKS_HOST=<workspace URL>
DATABRICKS_TOKEN=<secret>
DATABRICKS_CHURN_ENDPOINT=<endpoint>
DATABRICKS_CLV_ENDPOINT=<endpoint>
ML_CHURN_CLASS_ORDER=0,1
ML_INFERENCE_TIMEOUT_SECONDS=15
```

## Dependências dos artefatos (achado importante)

| Artefato | scikit-learn declarado | mlflow |
|---|---|---|
| churn_gb2 v1 | 1.9.1 | 3.17.2 |
| clv_gb v3 | **1.7.2** | 3.12.0 |

Os dois modelos exigem versões diferentes de scikit-learn, então **não podem
coexistir no mesmo ambiente Python**. Localmente o CLV não carrega com 1.9.1
(`ModuleNotFoundError: _loss`, módulo removido em versões novas do sklearn); isso
**não** é falta de xgboost (o pickle usa apenas `HistGradientBoosting` do sklearn).
Cada endpoint do Model Serving constrói seu próprio ambiente a partir do
`requirements.txt`/`conda.yaml` do modelo, o que resolve a incompatibilidade, desde
que o build do endpoint CLV conclua com sucesso. Não instale versões aleatórias
no backend. Se o build do endpoint falhar, registre uma nova versão do CLV com as
dependências corretas empacotadas e peça decisão explícita do time.

## Checklist para o responsável pelo Databricks

```text
[ ] Workspace Databricks identificado
[ ] Model Serving habilitado
[ ] workspace.default.churn_gb2 v1 disponível
[ ] workspace.default.clv_gb v3 disponível
[ ] Permissões do modelo verificadas
[ ] Endpoint Churn criado
[ ] Endpoint CLV criado
[ ] Endpoint Churn = READY
[ ] Endpoint CLV = READY
[ ] Churn testado
[ ] CLV testado
[ ] Dependências do CLV validadas (build do endpoint com scikit-learn 1.7.2)
[ ] Payload validado
[ ] Response validada
[ ] URL do workspace fornecida ao time
[ ] Secret/token configurado fora do Git
```

## Smoke test (executar por quem tem acesso)

1. Confirmar o estado do endpoint (`READY`) no workspace. Registrar endpoint,
   modelo e versão — nunca o token.
2. Churn: enviar uma linha com exatamente as 52 features (de um cliente real
   autorizado, sem CPF nem identificadores). Esperado: HTTP 200, `predictions`
   com 2 probabilidades `[p0, p1]`, `0 <= p1 <= 1`. Registrar `model_name`,
   `model_version`, formato da resposta e o score.
3. CLV: mesma linha. Esperado: HTTP 200, valor numérico finito. Em caso de falha,
   registrar modelo, versão, erro e dependência ausente/incompatível.
4. Se o formato da resposta divergir (ex.: classes em vez de probabilidades, ou
   chave diferente de `predictions`), o backend rejeita a resposta com
   `ModelInferenceError`; ajuste o registro/`predict_fn` do modelo em vez de
   mapear valores no backend.
5. Com `ML_INFERENCE_MODE=databricks`, subir o backend e enviar um arquivo
   `ML_FEATURES_52`; esperar `scoring_status=scored` e média de churn/CLV no
   resumo agregado.
