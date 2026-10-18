# Model inference

`churn_predictor.py` usa MLflow Serving por padrão. A inferência falha
explicitamente se `MLFLOW_SERVING_URL` não estiver configurado ou se o Serving
falhar. O fallback local heurístico só é habilitado explicitamente com
`MLFLOW_LOCAL_INFERENCE=true`; ele não carrega nem representa o modelo
registrado no MLflow. O adaptador de aplicação está em
`backend/app/services/inference_service.py`.
