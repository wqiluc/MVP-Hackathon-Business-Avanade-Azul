# Model training

`churn_trainer.py` executa o split 80/20 com `random_state=42`, treina o
RandomForest atual e retorna modelo, target de teste e predições para avaliação.
Tracking e persistência permanecem no módulo MLflow.
