# Model tracking

`mlflow_tracker.py` é a fronteira de tracking: experimento, run, parâmetros,
métricas, logging do modelo sklearn e acesso ao Model Registry. O logging do
RandomForest foi validado com `skops` e a allowlist necessária, incluindo
`sklearn.tree._tree.Tree`. O nome do modelo vem exclusivamente de
`MLFLOW_MODEL_NAME`, fornecido pelo ambiente; o alias esperado é `champion`.
Sem o nome, a consulta não acessa o Registry e o registro é rejeitado.

A disponibilidade de Registry/Serving não é garantida pelo repositório.
Compatibilidade depende das versões de MLflow, scikit-learn, skops e
dependências do modelo. Testes locais usam mocks; integração real é opt-in.
