import os
from fastapi import UploadFile, HTTPException, status

ALLOWED_EXTENSIONS = {"xlsx", "xls", "csv", "json"}

class UploadService:
    @staticmethod
    def validate_file_extension(filename: str) -> str:
        """
        Valida se a extensão do ficheiro é Excel (.xlsx) ou JSON conforme exigido pela mentoria.
        """
        if "." not in filename:
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
        os.makedirs("data/raw", exist_ok=True)
        temp_path = f"data/raw/temp_{file.filename}"

        try:
            contents = await file.read()
            if not contents:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="O ficheiro enviado está vazio."
                )

            with open(temp_path, "wb") as f:
                f.write(contents)

            return temp_path
        except Exception as e:
            if os.path.exists(temp_path):
                os.remove(temp_path)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Falha ao guardar o ficheiro temporário: {str(e)}"
            )

    @staticmethod
    def cleanup_temp_file(file_path: str) -> None:
        """
        Remove o ficheiro temporário do disco após o processamento no Data Lake.
        """
        if os.path.exists(file_path):
            os.remove(file_path)
