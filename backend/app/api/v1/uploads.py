from fastapi import APIRouter, Depends, UploadFile, File
from app.core.security import get_current_user
from app.schemas.upload_schema import UploadResponse
from app.services.upload_service import UploadService

router = APIRouter()


@router.post("/clientes")
async def ingerir_clientes(arquivo: UploadFile = File(...), current_user: dict = Depends(get_current_user)):
    """Contrato do front: recebe a base e roda Bronze → Silver → Gold + inferência."""
    resumo, tamanho = await UploadService.process_upload(arquivo)
    return {
        "arquivo": arquivo.filename, "tamanhoBytes": tamanho, "status": "recebido",
        "mensagem": f"{resumo['processed_rows']} clientes processados nas camadas Bronze, Silver e Gold.",
    }


@router.post("/ingest", response_model=UploadResponse)
async def upload_dataset(file: UploadFile = File(...), current_user: dict = Depends(get_current_user)):
    """Rota legada (/data/ingest)."""
    resumo, _ = await UploadService.process_upload(file)
    return UploadResponse(
        message="Base de dados processada com sucesso nas camadas Bronze, Silver e Gold!", details=resumo)
