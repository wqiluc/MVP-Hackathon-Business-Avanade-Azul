# Model tracking

`mlflow_tracker.py` é a fronteira de tracking: experimento, run, parâmetros,
métricas, logging do modelo sklearn e acesso ao Model Registry. O logging do
RandomForest foi validado com `skops` e a allowlist necessária, incluindo
`sklearn.tree._tree.Tree`. No fluxo real executado neste ambiente, o modelo foi
registrado, a versão ficou `READY`, o alias `champion` foi validado, o modelo
foi servido via MLflow Serving e a prediction real foi validada.

Validado no ambiente atual; compatibilidade em outros ambientes depende das
versões de MLflow, scikit-learn, skops e dependências do modelo.
