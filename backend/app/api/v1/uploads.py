from fastapi import APIRouter, Depends, UploadFile, File
from app.core.security import get_current_user
from app.schemas.upload_schema import UploadResponse
from app.services.upload_service import UploadService
from app.services.datalake_service import DataLakeService

router = APIRouter()

@router.post("/ingest", response_model=UploadResponse)
async def upload_dataset(file: UploadFile = File(...), current_user: dict = Depends(get_current_user)):
    """
    Recebe bases sintéticas em Excel (.xlsx) ou JSON e processa
    as camadas Bronze, Silver e Gold da Arquitetura Medalhão.
    """
    # 1. Valida a extensão (xlsx ou json)
    file_ext = UploadService.validate_file_extension(file.filename)

    # 2. Guarda temporariamente o ficheiro
    temp_path = await UploadService.save_temp_file(file)

    try:
        # 3. Processa no Data Lake Medalhão (DuckDB)
        summary = DataLakeService.process_ingestion(temp_path, file_ext)

        return UploadResponse(
            message="Base de dados processada com sucesso nas camadas Bronze, Silver e Gold!",
            details=summary
        )
    finally:
        # 4. Elimina o ficheiro temporário
        UploadService.cleanup_temp_file(temp_path)
