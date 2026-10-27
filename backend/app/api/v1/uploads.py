from fastapi import APIRouter, Depends, UploadFile, File
from app.core.security import get_current_user
from app.services.schemas.upload_schema import UploadResponse
from app.services.upload_service import UploadService

router = APIRouter()


@router.post("/clientes")
async def ingerir_clientes(arquivo: UploadFile = File(...), current_user: dict = Depends(get_current_user)):
    """Contrato do front: recebe a base e roda Bronze → Silver → Gold + inferência."""
    resumo, tamanho = await UploadService.process_upload(arquivo)
    message = f"{resumo['processed_rows']} clientes processados nas camadas Bronze, Silver e Gold."
    if resumo.get("status") == "scored_not_persisted":
        summary = resumo.get("scoring_summary", {})
        churn_ok = summary.get("churn_score_mean") is not None
        clv_ok = summary.get("clv_mean") is not None
        outcome = (
            "Churn e CLV calculados." if churn_ok and clv_ok
            else "Churn calculado; CLV indisponível." if churn_ok
            else "CLV calculado; Churn indisponível." if clv_ok
            else "Alguns scores estão indisponíveis."
        )
        message = (
            f"Arquivo processado. {outcome} {resumo['processed_rows']} registros. "
            "Contrato ML_FEATURES_52: nada foi publicado no snapshot CRM."
        )
    elif resumo.get("scoring_status") == "awaiting_model_registration":
        message += " Score pendente: treine e registre o modelo no MLflow para habilitar inferência."
    elif resumo.get("scoring_status") == "awaiting_model_features":
        message += (
            " Score de churn e CLV indisponíveis: o conjunto não contém todas "
            "as features exigidas pelos contratos dos modelos."
        )
    return {
        "arquivo": arquivo.filename, "tamanhoBytes": tamanho, "status": "recebido",
        "mensagem": message,
        "ingestion_contract": resumo.get("ingestion_contract"),
        **({"scoring_summary": resumo["scoring_summary"]} if "scoring_summary" in resumo else {}),
    }


@router.post("/ingest", response_model=UploadResponse, response_model_exclude_none=True)
async def upload_dataset(file: UploadFile = File(...), current_user: dict = Depends(get_current_user)):
    """Rota legada (/data/ingest)."""
    resumo, _ = await UploadService.process_upload(file)
    return UploadResponse(
        message="Base de dados processada com sucesso nas camadas Bronze, Silver e Gold!", details=resumo)
