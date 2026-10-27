"""Executa um modelo MLflow local em um interpretador Python dedicado.

Este script roda fora do processo da API, com as dependências pinadas pelo
próprio artefato (por exemplo, o scikit-learn exigido pelo CLV). Ele não importa
nada de `app`. Lê do stdin um JSON {"model_path", "method", "frame"} e escreve no
stdout {"predictions", "classes"}.
"""

import json
import sys


def main() -> int:
    import mlflow.sklearn
    import numpy as np
    import pandas as pd

    request = json.load(sys.stdin)
    frame = pd.DataFrame(
        request["frame"]["data"], columns=request["frame"]["columns"]
    )
    model = mlflow.sklearn.load_model(request["model_path"])
    predictor = getattr(model, request["method"], None)
    if not callable(predictor):
        print(f"Model does not support {request['method']}.", file=sys.stderr)
        return 2
    predictions = np.asarray(predictor(frame)).tolist()
    classes = (
        np.asarray(model.classes_).tolist() if hasattr(model, "classes_") else None
    )
    json.dump({"predictions": predictions, "classes": classes}, sys.stdout)
    return 0


if __name__ == "__main__":
    sys.exit(main())
