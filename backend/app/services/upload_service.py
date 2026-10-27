import logging
import os
import tempfile
from fastapi import UploadFile, HTTPException, status
from starlette.concurrency import run_in_threadpool
from app.config import BASE_DIR, settings
from app.services.datalake_service import DataLakeService
from app.services.snapshot import SnapshotBusyError, ingestion_run
from data.ingestion.file_reader import FileContractError

ALLOWED_EXTENSIONS = {"xlsx", "xls", "csv", "json"}
logger = logging.getLogger(__name__)

class UploadService:
    @staticmethod
    def validate_file_extension(filename: str | None) -> str:
        """
        Valida se a extensão do ficheiro é Excel (.xlsx) ou JSON conforme exigido pela mentoria.
        """
        if not filename or "." not in filename:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="O ficheiro enviado não possui uma extensão válida."
            )

        extension = filename.rsplit(".", 1)[1].lower()

        if extension not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Formato não permitido. Envie ficheiros Excel (.xlsx/.xls), CSV ou JSON."
            )

        return extension

    @staticmethod
    async def save_temp_file(file: UploadFile) -> str:
        """
        Guarda o ficheiro temporariamente no disco para ser processado pelo DataLakeService.
        """
        upload_dir = BASE_DIR / "data" / "raw"
        os.makedirs(upload_dir, exist_ok=True)
        temp_path = None

        try:
            contents = await file.read(settings.MAX_UPLOAD_BYTES + 1)
            if len(contents) > settings.MAX_UPLOAD_BYTES:
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail=f"O arquivo excede o limite de {settings.MAX_UPLOAD_BYTES} bytes.",
                )
            if not contents:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="O ficheiro enviado está vazio."
                )

            with tempfile.NamedTemporaryFile(
                mode="wb",
                dir=upload_dir,
                prefix="upload-",
                suffix=f".{file.filename.rsplit('.', 1)[1].lower()}",
                delete=False,
            ) as f:
                temp_path = f.name
                f.write(contents)

            return temp_path
        except HTTPException:
            if temp_path and os.path.exists(temp_path):
                os.remove(temp_path)
            raise
        except OSError as error:
            if temp_path and os.path.exists(temp_path):
                os.remove(temp_path)
            logger.error("Could not save uploaded dataset; type=%s", type(error).__name__)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Falha ao guardar o arquivo enviado.",
            ) from error

    @staticmethod
    def cleanup_temp_file(file_path: str) -> None:
        """
        Remove o ficheiro temporário do disco após o processamento no Data Lake.
        """
        if os.path.exists(file_path):
            os.remove(file_path)

    @classmethod
    async def process_upload(cls, file: UploadFile) -> tuple[dict, int]:
        with ingestion_run(settings.DATA_LAKE_BACKEND):
            return await cls._process_upload(file)

    @classmethod
    async def _process_upload(cls, file: UploadFile) -> tuple[dict, int]:
        file_ext = cls.validate_file_extension(file.filename)
        temp_path = await cls.save_temp_file(file)
        try:
            tamanho = os.path.getsize(temp_path)
            try:
                resumo = await run_in_threadpool(
                    DataLakeService.process_ingestion, temp_path, file_ext,
                )
                return resumo, tamanho
            except SnapshotBusyError as error:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=str(error),
                ) from error
            except FileContractError as error:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail={
                        "message": str(error),
                        "missing_columns": error.missing_columns,
                        "invalid_columns": error.invalid_columns,
                        "ingestion_contract": error.ingestion_contract,
                    },
                ) from error
            except ValueError as error:
                logger.warning("Dataset rejected; type=%s", type(error).__name__)
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Não foi possível processar os dados enviados. Verifique o arquivo.",
                ) from error
        finally:
            cls.cleanup_temp_file(temp_path)
