# Model inference

`churn_predictor.py` usa MLflow Serving por padrão. A inferência falha
explicitamente se `MLFLOW_SERVING_URL` não estiver configurado ou se o Serving
falhar. Não há fallback heurístico para scores, mesmo com a flag legada
`MLFLOW_LOCAL_INFERENCE=true`. Sem Tracking/modelo configurado, a ingestão
mantém scores nulos em vez de chamar o predictor. O adaptador de aplicação está em
`backend/app/services/inference_service.py`.
