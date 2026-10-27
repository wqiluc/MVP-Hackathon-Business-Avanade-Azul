# Machine learning e MLflow

- `ml/features/training_dataset.py`: seleciona as cinco features na ordem
  `frequency`, `recency_days`, `total_spend`, `flight_incidents`, `avg_ticket`,
  aplica `fillna(0)` às features e usa `high_risk_flag` como target.
- `ml/training/churn_trainer.py`: split 80/20 com `random_state=42` e
  `RandomForestClassifier(n_estimators=100, max_depth=8, random_state=42)`;
  retorna modelo, target de teste e predições para avaliação.
- `ml/evaluation/metrics.py`: accuracy, precision e recall; precision/recall
  usam `zero_division=0`.
- `ml/inference/churn_predictor.py`: inferência pelo MLflow Serving; não
  substitui modelo ausente por scores heurísticos.
- `ml/models/mlflow_tracker.py`: configuração do Tracking, experimento, run,
  logging de parâmetros/métricas/modelo e promoção/consulta do alias `champion`
  no Model Registry.
- `backend/app/services/ml_service.py`: coordenação e contrato do serviço; não
  lê DuckDB diretamente.

## Treino, avaliação e inferência

O dataset de treino usa cinco features na ordem descrita acima e `high_risk_flag`
como target. O target é derivado da regra
`flight_incidents >= 2` ou `recency_days > 60`, não de evasão observada.
Consequentemente, as métricas medem concordância com essa proxy, não desempenho
comprovado de previsão de churn real. `churn_score` é a probabilidade da classe
positiva para esse target e não deve ser confundido com o indicador da regra.

O treinamento é explícito e administrativo; não ocorre no startup. O serviço
avalia e envia parâmetros, métricas e modelo ao Tracking configurado. O
predictor usa MLflow Serving; se Tracking/modelo não estiverem configurados no
desenvolvimento, o pipeline pode manter `churn_score` nulo. Uma integração
configurada que falha não é substituída por score heurístico ou inferência
local automática.

`high_risk_flag` é calculado por regra (`flight_incidents >= 2` ou
`recency_days > 60`) e funciona apenas como proxy supervisionada; não é churn
observado. Portanto, accuracy, precision e recall descrevem a classificação
desse target derivado, não a previsão de churn real. `churn_score` é a
probabilidade de classe positiva do modelo e não deve ser confundida com
`high_risk_flag` nem com churn observado.

## Modelos empacotados de churn e CLV

O scoring de CRM também suporta os artefatos fornecidos em `modelo_churn/` e
`pacote_CLV/`. Esse contrato é independente do pipeline legado de treino de
cinco features documentado acima. Os dois artefatos exigem os mesmos 52 nomes
de entrada; a lista canônica e os tipos estão em
`backend/app/services/ml/model_contracts.py`. O `FeatureBuilder` rejeita
features ausentes, tipos incompatíveis, nulos e valores numéricos não finitos.
Não há aliases, valores padrão, cálculo de features nem conversão do contrato
canônico de upload para o contrato dos modelos.

O upload atual contém somente `id_cliente`, `tier`, `frequencia`,
`recencia_dias`, `gasto_total` e `incidentes`. Portanto, não fornece as 52
features e não é fonte suficiente para esses modelos: `churn_score` e CLV ficam
indisponíveis (`NULL`), e a resposta de upload informa a lacuna. Não se usa o
dataset de exemplo do artefato como dados de clientes nem o classificador proxy
de cinco features como substituto. Quando uma origem futura entregar o contrato
completo, o churn seleciona a probabilidade pelo rótulo da classe `1`; o CLV
retorna a saída numérica escalar do horizonte de 12 meses informado pelo
artefato.

`ML_INFERENCE_MODE=local` carrega cada modelo MLflow empacotado sob demanda,
usando `ML_CHURN_MODEL_PATH` e `ML_CLV_MODEL_PATH`. `ML_INFERENCE_MODE=databricks`
usa os endpoints configurados por `DATABRICKS_HOST`, `DATABRICKS_TOKEN`,
`DATABRICKS_CHURN_ENDPOINT` e `DATABRICKS_CLV_ENDPOINT`; o token fica somente
no backend. `ML_CHURN_CLASS_ORDER` declara a ordem das classes para o endpoint
remoto e deve corresponder aos rótulos observados no artefato. Ambos os modos
usam `ML_INFERENCE_TIMEOUT_SECONDS`. Em produção, o startup valida o provider
selecionado; readiness verifica os dois endpoints Databricks ou reporta o
provider local configurado. Não há fallback automático entre providers.

Modelos oficiais: churn `workspace.default.churn_gb2` versão 1 e CLV
`workspace.default.clv_gb` versão 3. O notebook `CLVtest.ipynb` (XGBoost no
Snowflake, saída em `GOLD.CLV_PREVISTO`) é apenas evidência de outra
implementação e não é o modelo de CLV da aplicação nem é consumido por ela.

Bloqueio externo atual: a origem das 52 features (provavelmente
`AZUL_DATA_LAKE.SILVER.CLIENTES_CLEAN`) não foi validada, pois seu schema real e
o vínculo entre `id_cliente` e `CLIENTE_ID` são desconhecidos. Até que sejam
confirmados, a aplicação não lê essa tabela. Um E2E real exige acesso ao
Snowflake e ao Databricks Model Serving (ou runtime MLflow isolado).

O ambiente backend validado usa scikit-learn 1.9.1 para o artefato de churn.
O pacote CLV declara scikit-learn 1.7.2 e não carregou nesse runtime por
incompatibilidade de dependência (`_loss`). Não se deve atualizar o ambiente
compartilhado nem substituir o modelo para contornar isso: use um ambiente
isolado compatível com o pacote ou o endpoint Databricks. Chamadas externas
foram exercitadas somente com HTTP mockado; a disponibilidade real de serving
não foi validada.

O nome exato do modelo no Registry é fornecido por `MLFLOW_MODEL_NAME`, sem
renomear modelos externos existentes. O registro promove a versão
validada ao alias `champion`. O teste `test_mlflow_integration.py` pode iniciar
um Tracking e Serving MLflow locais isolados ao habilitar
`MLFLOW_INTEGRATION_TESTS=1`; isso valida a integração local, não a
disponibilidade de uma instância remota de produção.

Tracking e Serving são serviços separados e opcionais para desenvolvimento.
O `npm start` só inicia Tracking local quando `MLFLOW_TRACKING_URI` é configurada
explicitamente; após registrar um modelo, o Serving deve ser iniciado
separadamente em `http://localhost:5001`. Consulte
[`infrastructure/mlflow/README.md`](../../infrastructure/mlflow/README.md) para
comandos de inicialização, armazenamento local, Registry e testes de
integração. A disponibilidade de Tracking/Registry/Serving externo não é
garantida pelo repositório.

O erro de tipo não confiável `sklearn.tree._tree.Tree` foi reproduzido com
Python 3.12.15, MLflow 3.17.1, scikit-learn 1.9.1 e skops 0.16.0. O logging
agora confia explicitamente somente nesse tipo interno de árvore para o
RandomForest criado pelo treino do projeto; erros de logging ou registro seguem
propagados e não são convertidos em sucesso.

O nome exato do modelo registrado é definido pelo ambiente (`MLFLOW_MODEL_NAME`)
e não deve ser renomeado como parte de uma mudança de branding sem migração do
Registry e dos consumidores. O alias esperado é `champion`. O guia em
`infrastructure/mlflow/README.md` contém os passos locais de Tracking, treino,
Serving e testes reais opt-in.

## Contratos de ingestão

O upload reconhece explicitamente dois contratos, detectados por nomes exatos
de colunas (`backend/app/services/ml/ingestion_contracts.py`):

| Contrato | Colunas | Situação |
|---|---|---|
| `CRM_CANONICAL` | `id_cliente, tier, recencia_dias, frequencia, gasto_total, incidentes` | Processado (Bronze → Silver → Gold). |
| `ML_FEATURES_52` | As 52 features de `CHURN_FEATURES` (fonte única: `model_contracts.py`) | Aceito para **scoring**: Churn e CLV oficiais rodam sobre as 52 features; `churn_180d`, `clv_12m`, `cpf` e demais colunas são descartadas antes do modelo. Nada é publicado no snapshot CRM nem persistido; a resposta traz só um resumo agregado (sem IDs). |

- No scoring `ML_FEATURES_52`, Churn e CLV são independentes: se um modelo estiver
  indisponível (`ModelInferenceError`), seu agregado vem `null` e `scoring_status`
  fica `partial` (ou `unavailable` se ambos falharem). Não há fórmula substituta nem HTTP 500.
- A prioridade é ML > CRM > `UNKNOWN`; `UNKNOWN` é rejeitado listando os contratos aceitos.
- `churn_180d` e `clv_12m` são alvos de treino, não entradas de inferência; sua
  presença não altera a detecção e nunca chega ao modelo.
- Não há aliases (`frequencia → voos_12m`, `gasto_total → gasto_total_12m`,
  `incidentes → n_cancelamentos_12m`): não existe mapeamento oficial entre o
  contrato ML e os campos do CRM. Enquanto não existir, `ML_FEATURES_52` não é
  processado, e Churn/CLV reais continuam dependendo das 52 features.
- A API devolve `ingestion_contract` nas respostas de sucesso e nos erros 422.
