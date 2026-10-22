# ML atual

- `ml/features/training_dataset.py`: seleciona as cinco features na ordem
  `frequency`, `recency_days`, `total_spend`, `flight_incidents`, `avg_ticket`,
  aplica `fillna(0)` às features e usa `high_risk_flag` como target.
- `ml/training/churn_trainer.py`: `train_test_split(test_size=0.2,
  random_state=42)` e `RandomForestClassifier(n_estimators=100, max_depth=8,
  random_state=42)`.
- `ml/evaluation/metrics.py`: accuracy, precision e recall.
- `ml/inference/churn_predictor.py`: inferência pelo MLflow Serving; não
  substitui modelo ausente por scores heurísticos.
- `ml/models/mlflow_tracker.py`: configuração do Tracking, experimento, run,
  logging de parâmetros/métricas/modelo e promoção/consulta do alias `champion`
  no Model Registry.
- `backend/app/services/ml_service.py`: coordenação e contrato do serviço; não
  lê DuckDB diretamente.

`high_risk_flag` é calculado por regra (`flight_incidents >= 2` ou
`recency_days > 60`) e funciona apenas como proxy supervisionada; não é churn
observado. Portanto, accuracy, precision e recall descrevem a classificação
desse target derivado, não a previsão de churn real. `churn_score` é a
probabilidade de classe positiva do modelo e não deve ser confundida com
`high_risk_flag` nem com churn observado.

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
comandos de inicialização e testes de integração.

O erro de tipo não confiável `sklearn.tree._tree.Tree` foi reproduzido com
Python 3.12.15, MLflow 3.17.1, scikit-learn 1.9.1 e skops 0.16.0. O logging
agora confia explicitamente somente nesse tipo interno de árvore para o
RandomForest criado pelo treino do projeto; erros de logging ou registro seguem
propagados e não são convertidos em sucesso.
