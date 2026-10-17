import os
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, status
from app.core.security import get_current_user
from app.schemas.upload_schema import UploadResponse
from app.services.upload_service import UploadService
from app.services.datalake_service import DataLakeService

router = APIRouter()


async def _processar(file: UploadFile) -> tuple[dict, int]:
    file_ext = UploadService.validate_file_extension(file.filename)
    temp_path = await UploadService.save_temp_file(file)
    try:
        tamanho = os.path.getsize(temp_path)
        try:
            return DataLakeService.process_ingestion(temp_path, file_ext), tamanho
        except ValueError as e:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    finally:
        UploadService.cleanup_temp_file(temp_path)


@router.post("/clientes")
async def ingerir_clientes(arquivo: UploadFile = File(...), current_user: dict = Depends(get_current_user)):
    """Contrato do front: recebe a base e roda Bronze → Silver → Gold + inferência."""
    resumo, tamanho = await _processar(arquivo)
    return {
        "arquivo": arquivo.filename, "tamanhoBytes": tamanho, "status": "recebido",
        "mensagem": f"{resumo['processed_rows']} clientes processados nas camadas Bronze, Silver e Gold.",
    }


@router.post("/ingest", response_model=UploadResponse)
async def upload_dataset(file: UploadFile = File(...), current_user: dict = Depends(get_current_user)):
    """Rota legada (/data/ingest)."""
    resumo, _ = await _processar(file)
    return UploadResponse(
        message="Base de dados processada com sucesso nas camadas Bronze, Silver e Gold!", details=resumo)
