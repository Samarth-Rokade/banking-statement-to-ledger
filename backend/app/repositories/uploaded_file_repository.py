import uuid

from sqlalchemy.orm import Session

from app.models.uploaded_file import FileType, UploadedFile


class UploadedFileRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, uploaded_file_id: uuid.UUID) -> UploadedFile | None:
        return self.db.get(UploadedFile, uploaded_file_id)

    def create(
        self,
        user_id: uuid.UUID,
        original_filename: str,
        storage_path: str,
        file_type: FileType,
        file_size_bytes: int,
        checksum_sha256: str,
    ) -> UploadedFile:
        uploaded_file = UploadedFile(
            user_id=user_id,
            original_filename=original_filename,
            storage_path=storage_path,
            file_type=file_type,
            file_size_bytes=file_size_bytes,
            checksum_sha256=checksum_sha256,
        )
        self.db.add(uploaded_file)
        self.db.commit()
        self.db.refresh(uploaded_file)
        return uploaded_file
