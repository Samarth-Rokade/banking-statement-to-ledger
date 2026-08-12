import uuid
from unittest.mock import MagicMock, patch

import pytest

from app.upload.storage import GCSFileStorage, LocalDiskStorage, _parse_gs_uri, get_file_storage


def test_local_disk_storage_round_trips_content(tmp_path):
    storage = LocalDiskStorage(base_dir=str(tmp_path))
    user_id = uuid.uuid4()

    storage_path = storage.save(user_id, "statement.pdf", b"pdf bytes here")

    assert str(tmp_path) in storage_path
    assert storage.read(storage_path) == b"pdf bytes here"


def test_local_disk_storage_namespaces_by_user(tmp_path):
    storage = LocalDiskStorage(base_dir=str(tmp_path))
    user_a, user_b = uuid.uuid4(), uuid.uuid4()

    path_a = storage.save(user_a, "same-name.csv", b"a's content")
    path_b = storage.save(user_b, "same-name.csv", b"b's content")

    assert path_a != path_b
    assert storage.read(path_a) == b"a's content"
    assert storage.read(path_b) == b"b's content"


def test_parse_gs_uri_splits_bucket_and_blob():
    assert _parse_gs_uri("gs://my-bucket/user-id/some-file.pdf") == (
        "my-bucket",
        "user-id/some-file.pdf",
    )


def test_parse_gs_uri_rejects_non_gs_uri():
    with pytest.raises(ValueError):
        _parse_gs_uri("/local/path.pdf")


def test_gcs_file_storage_requires_bucket_name():
    with patch("google.cloud.storage.Client"):
        with pytest.raises(ValueError):
            GCSFileStorage(bucket_name="")


def test_gcs_file_storage_save_uploads_and_returns_gs_uri():
    mock_blob = MagicMock()
    mock_bucket = MagicMock()
    mock_bucket.blob.return_value = mock_blob
    mock_client = MagicMock()
    mock_client.bucket.return_value = mock_bucket

    with patch("google.cloud.storage.Client", return_value=mock_client):
        storage = GCSFileStorage(bucket_name="my-bucket")
        user_id = uuid.uuid4()
        result = storage.save(user_id, "statement.pdf", b"pdf bytes")

    assert result.startswith(f"gs://my-bucket/{user_id}/")
    assert result.endswith("_statement.pdf")
    mock_blob.upload_from_string.assert_called_once_with(b"pdf bytes")


def test_gcs_file_storage_read_downloads_from_the_uri_it_was_given():
    mock_blob = MagicMock()
    mock_blob.download_as_bytes.return_value = b"downloaded content"
    mock_bucket = MagicMock()
    mock_bucket.blob.return_value = mock_blob
    mock_client = MagicMock()
    mock_client.bucket.return_value = mock_bucket

    with patch("google.cloud.storage.Client", return_value=mock_client):
        storage = GCSFileStorage(bucket_name="my-bucket")
        content = storage.read("gs://other-bucket/some/key.pdf")

    mock_client.bucket.assert_called_with("other-bucket")
    mock_bucket.blob.assert_called_with("some/key.pdf")
    assert content == b"downloaded content"


def test_get_file_storage_returns_local_by_default(monkeypatch):
    from app.config.settings import get_settings

    monkeypatch.setattr(get_settings(), "storage_backend", "local")
    assert isinstance(get_file_storage(), LocalDiskStorage)


def test_get_file_storage_returns_gcs_when_configured(monkeypatch):
    from app.config.settings import get_settings

    monkeypatch.setattr(get_settings(), "storage_backend", "gcs")
    monkeypatch.setattr(get_settings(), "gcs_bucket_name", "my-bucket")

    with patch("google.cloud.storage.Client"):
        assert isinstance(get_file_storage(), GCSFileStorage)
