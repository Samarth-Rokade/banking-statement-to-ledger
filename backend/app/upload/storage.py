import uuid
from pathlib import Path
from typing import Protocol

from app.config.settings import get_settings


class FileStorage(Protocol):
    def save(self, user_id: uuid.UUID, filename: str, content: bytes) -> str:
        """Persist file content and return a storage_path that `open_for_read` can resolve later."""
        ...


class LocalDiskStorage:
    def __init__(self, base_dir: str | None = None):
        self.base_dir = Path(base_dir or get_settings().storage_dir)

    def save(self, user_id: uuid.UUID, filename: str, content: bytes) -> str:
        user_dir = self.base_dir / str(user_id)
        user_dir.mkdir(parents=True, exist_ok=True)
        stored_name = f"{uuid.uuid4()}_{filename}"
        target_path = user_dir / stored_name
        target_path.write_bytes(content)
        return str(target_path)
