import uuid
from pathlib import Path
from typing import Protocol

from app.config.settings import get_settings


class FileStorage(Protocol):
    def save(self, user_id: uuid.UUID, filename: str, content: bytes) -> str:
        """Persist file content and return a storage_path that `read` can resolve later."""
        ...

    def read(self, storage_path: str) -> bytes:
        """Retrieve content previously persisted by `save`, given the storage_path it returned."""
        ...


class LocalDiskStorage:
    """Dev-only: Cloud Run containers are ephemeral and don't share a filesystem
    across instances, so a file saved by one instance may not exist when a
    different instance later tries to process it. Production uses GCSFileStorage.
    """

    def __init__(self, base_dir: str | None = None):
        self.base_dir = Path(base_dir or get_settings().storage_dir)

    def save(self, user_id: uuid.UUID, filename: str, content: bytes) -> str:
        user_dir = self.base_dir / str(user_id)
        user_dir.mkdir(parents=True, exist_ok=True)
        stored_name = f"{uuid.uuid4()}_{filename}"
        target_path = user_dir / stored_name
        target_path.write_bytes(content)
        return str(target_path)

    def read(self, storage_path: str) -> bytes:
        return Path(storage_path).read_bytes()


class GCSFileStorage:
    """Production storage backend: uploaded files live in a Google Cloud Storage
    bucket instead of on the (ephemeral, per-instance) container filesystem.
    storage_path is stored as a `gs://bucket/key` URI, self-describing so it
    doesn't depend on whatever bucket happens to be configured at read time.
    """

    def __init__(self, bucket_name: str | None = None):
        from google.cloud import storage as gcs

        self.bucket_name = bucket_name or get_settings().gcs_bucket_name
        if not self.bucket_name:
            raise ValueError("GCS_BUCKET_NAME must be set to use GCSFileStorage.")
        self._client = gcs.Client()

    def save(self, user_id: uuid.UUID, filename: str, content: bytes) -> str:
        blob_name = f"{user_id}/{uuid.uuid4()}_{filename}"
        blob = self._client.bucket(self.bucket_name).blob(blob_name)
        blob.upload_from_string(content)
        return f"gs://{self.bucket_name}/{blob_name}"

    def read(self, storage_path: str) -> bytes:
        bucket_name, blob_name = _parse_gs_uri(storage_path)
        blob = self._client.bucket(bucket_name).blob(blob_name)
        return blob.download_as_bytes()


def _parse_gs_uri(uri: str) -> tuple[str, str]:
    if not uri.startswith("gs://"):
        raise ValueError(f"Not a gs:// URI: {uri!r}")
    bucket_name, _, blob_name = uri.removeprefix("gs://").partition("/")
    return bucket_name, blob_name


def get_file_storage() -> FileStorage:
    """Selects the storage backend from settings - the single place upload and
    processing code should go through, rather than constructing LocalDiskStorage
    or GCSFileStorage directly, so switching STORAGE_BACKEND is the only change
    needed to move between dev and production.
    """
    if get_settings().storage_backend == "gcs":
        return GCSFileStorage()
    return LocalDiskStorage()
