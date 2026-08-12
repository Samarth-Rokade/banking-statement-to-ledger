import hashlib
import uuid

from fastapi import HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.config.settings import get_settings
from app.models.processing_job import ProcessingJob
from app.models.uploaded_file import FileType
from app.repositories.job_repository import JobRepository
from app.repositories.uploaded_file_repository import UploadedFileRepository
from app.upload.storage import FileStorage, get_file_storage

_EXTENSION_TO_FILE_TYPE = {
    "pdf": FileType.PDF,
    "csv": FileType.CSV,
    "xlsx": FileType.XLSX,
    "xls": FileType.XLSX,
}


class UploadService:
    def __init__(self, db: Session, storage: FileStorage | None = None):
        self.db = db
        self.storage = storage or get_file_storage()
        self.file_repo = UploadedFileRepository(db)
        self.job_repo = JobRepository(db)
        self.settings = get_settings()

    def _resolve_file_type(self, filename: str) -> FileType:
        extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        file_type = _EXTENSION_TO_FILE_TYPE.get(extension)
        if file_type is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Unsupported file type. Only PDF, CSV, and Excel files are accepted.",
            )
        return file_type

    def handle_upload(self, user_id: uuid.UUID, file: UploadFile, content: bytes) -> ProcessingJob:
        if not file.filename:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Filename is required")

        file_type = self._resolve_file_type(file.filename)

        if len(content) == 0:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded file is empty")
        if len(content) > self.settings.max_upload_size_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                detail=f"File exceeds maximum size of {self.settings.max_upload_size_bytes} bytes",
            )

        checksum = hashlib.sha256(content).hexdigest()
        storage_path = self.storage.save(user_id, file.filename, content)

        uploaded_file = self.file_repo.create(
            user_id=user_id,
            original_filename=file.filename,
            storage_path=storage_path,
            file_type=file_type,
            file_size_bytes=len(content),
            checksum_sha256=checksum,
        )
        return self.job_repo.create(uploaded_file.id)
