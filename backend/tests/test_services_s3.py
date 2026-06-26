"""Tests for S3 sync service – mocked boto3 and RAG."""

import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.s3 import (
    _build_s3_url,
    _decrypt_credentials,
    _download_object,
    _get_s3_client,
    _list_objects,
    sync_s3_prefix,
)


def test_get_s3_client_basic():
    with patch("boto3.client") as mock_client:
        _get_s3_client({"access_key": "ak", "secret_key": "sk", "region": "us-west-2"})
        mock_client.assert_called_once()
        call_kwargs = mock_client.call_args
        assert call_kwargs.args[0] == "s3"
        assert call_kwargs.kwargs["aws_access_key_id"] == "ak"
        assert call_kwargs.kwargs["region_name"] == "us-west-2"


def test_get_s3_client_with_endpoint():
    with patch("boto3.client") as mock_client:
        _get_s3_client({"access_key": "ak", "secret_key": "sk", "endpoint_url": "http://minio:9000"})
        call_kwargs = mock_client.call_args
        assert call_kwargs.kwargs["endpoint_url"] == "http://minio:9000"


def test_decrypt_credentials_json():
    from cryptography.fernet import Fernet
    from app.core.config import settings
    old_key = settings.fernet_key
    settings.fernet_key = Fernet.generate_key().decode()
    try:
        from app.core.encryption import EncryptionService
        crypto = EncryptionService()
        creds = {"access_key": "ak", "secret_key": "sk"}
        encrypted = crypto.encrypt(json.dumps(creds))
        result = _decrypt_credentials(encrypted)
        assert result == creds
    finally:
        settings.fernet_key = old_key


def test_decrypt_credentials_literal_eval():
    from cryptography.fernet import Fernet
    from app.core.config import settings
    old_key = settings.fernet_key
    settings.fernet_key = Fernet.generate_key().decode()
    try:
        from app.core.encryption import EncryptionService
        crypto = EncryptionService()
        creds_str = "{'access_key': 'ak', 'secret_key': 'sk'}"
        encrypted = crypto.encrypt(creds_str)
        result = _decrypt_credentials(encrypted)
        assert result["access_key"] == "ak"
    finally:
        settings.fernet_key = old_key


def test_list_objects_filters_unsupported():
    mock_client = MagicMock()
    mock_paginator = MagicMock()
    mock_paginator.paginate.return_value = [
        {"Contents": [
            {"Key": "doc.txt", "Size": 100},
            {"Key": "image.png", "Size": 200},
            {"Key": "data.csv", "Size": 50},
            {"Key": "folder/", "Size": 0},
        ]}
    ]
    mock_client.get_paginator.return_value = mock_paginator

    objects = _list_objects(mock_client, "bucket", "prefix/")
    keys = [o["Key"] for o in objects]
    assert "doc.txt" in keys
    assert "data.csv" in keys
    assert "image.png" not in keys
    assert "folder/" not in keys


def test_list_objects_empty():
    mock_client = MagicMock()
    mock_paginator = MagicMock()
    mock_paginator.paginate.return_value = [{}]
    mock_client.get_paginator.return_value = mock_paginator

    objects = _list_objects(mock_client, "bucket", "prefix/")
    assert objects == []


def test_download_object():
    mock_client = MagicMock()
    mock_body = MagicMock()
    mock_body.read.return_value = b"file content"
    mock_client.get_object.return_value = {"Body": mock_body}

    content = _download_object(mock_client, "bucket", "key.txt")
    assert content == b"file content"


def test_build_s3_url_with_endpoint():
    url = _build_s3_url({"endpoint_url": "http://minio:9000"}, "mybucket", "path/file.txt")
    assert url == "http://minio:9000/mybucket/path/file.txt"


def test_build_s3_url_us_east_1():
    url = _build_s3_url({"region": "us-east-1"}, "mybucket", "file.txt")
    assert url == "https://s3.amazonaws.com/mybucket/file.txt"


def test_build_s3_url_other_region():
    url = _build_s3_url({"region": "eu-west-1"}, "mybucket", "file.txt")
    assert url == "https://s3.eu-west-1.amazonaws.com/mybucket/file.txt"


def test_build_s3_url_default_region():
    url = _build_s3_url({}, "mybucket", "file.txt")
    assert url == "https://s3.amazonaws.com/mybucket/file.txt"


def test_sync_s3_prefix_no_objects():
    with patch.object(sync_s3_prefix, "retry", MagicMock()) as mock_retry:
        with patch("app.services.s3._decrypt_credentials", return_value={"access_key": "ak"}), \
             patch("app.services.s3._get_s3_client"), \
             patch("app.services.s3._list_objects", return_value=[]), \
             patch("app.services.s3.asyncio") as mock_asyncio, \
             patch("app.services.s3.EncryptionService"):

            mock_asyncio.run = lambda coro: _run_coro_sync(coro)

            with patch("app.services.s3._update_source_status", new=AsyncMock()):
                result = sync_s3_prefix.run(
                    bucket="mybucket",
                    prefix="data/",
                    source_title="Test Source",
                    connector_credentials="encrypted_creds",
                    knowledge_source_id="ks-1",
                    slug="test-src",
                )
                assert result["status"] == "ok"
                assert result["objects"] == 0


def test_sync_s3_prefix_with_objects():
    with patch.object(sync_s3_prefix, "retry", MagicMock()):
        mock_objects = [
            {"Key": "data/file1.txt", "Size": 100, "LastModified": datetime(2024, 1, 1, tzinfo=timezone.utc)},
            {"Key": "data/file2.csv", "Size": 200, "LastModified": datetime(2024, 1, 2, tzinfo=timezone.utc)},
        ]

        with patch("app.services.s3._decrypt_credentials", return_value={"access_key": "ak"}), \
             patch("app.services.s3._get_s3_client"), \
             patch("app.services.s3._list_objects", return_value=mock_objects), \
             patch("app.services.s3._download_object", return_value=b"file content"), \
             patch("app.services.s3.parse_upload", return_value="parsed text"), \
             patch("app.services.s3._build_s3_url", return_value="https://s3.amazonaws.com/bucket/key"), \
             patch("app.services.s3._detect_file_type", return_value="txt"), \
             patch("app.services.s3.RAGService") as mock_rag_cls, \
             patch("app.services.s3.asyncio") as mock_asyncio, \
             patch("app.services.s3.EncryptionService"):

            mock_rag = mock_rag_cls.return_value
            mock_rag.delete_by_knowledge_source = AsyncMock()
            mock_rag.get_source_metadata = AsyncMock(return_value={})
            mock_rag.ingest_document = AsyncMock(return_value=5)
            mock_rag.delete_by_source_id = AsyncMock()

            with patch("app.services.s3._update_source_status", new=AsyncMock()):
                mock_asyncio.run = lambda coro: _run_coro_sync(coro)

                result = sync_s3_prefix.run(
                    bucket="mybucket",
                    prefix="data/",
                    source_title="Test Source",
                    connector_credentials="encrypted_creds",
                    knowledge_source_id="ks-1",
                    slug="test-src",
                )
                assert result["status"] == "ok"
                assert result["objects"] == 2
                assert mock_rag.ingest_document.call_count == 2


def test_sync_s3_prefix_force_full():
    with patch.object(sync_s3_prefix, "retry", MagicMock()):
        mock_objects = [
            {"Key": "data/file1.txt", "Size": 100, "LastModified": datetime(2024, 1, 1, tzinfo=timezone.utc)},
        ]

        with patch("app.services.s3._decrypt_credentials", return_value={"access_key": "ak"}), \
             patch("app.services.s3._get_s3_client"), \
             patch("app.services.s3._list_objects", return_value=mock_objects), \
             patch("app.services.s3._download_object", return_value=b"content"), \
             patch("app.services.s3.parse_upload", return_value="text"), \
             patch("app.services.s3._build_s3_url", return_value="url"), \
             patch("app.services.s3._detect_file_type", return_value="txt"), \
             patch("app.services.s3.RAGService") as mock_rag_cls, \
             patch("app.services.s3.asyncio") as mock_asyncio, \
             patch("app.services.s3.EncryptionService"):

            mock_rag = mock_rag_cls.return_value
            mock_rag.delete_by_knowledge_source = AsyncMock()
            mock_rag.get_source_metadata = AsyncMock(return_value={})
            mock_rag.ingest_document = AsyncMock(return_value=3)
            mock_rag.delete_by_source_id = AsyncMock()

            with patch("app.services.s3._update_source_status", new=AsyncMock()):
                mock_asyncio.run = lambda coro: _run_coro_sync(coro)

                result = sync_s3_prefix.run(
                    bucket="mybucket",
                    prefix="data/",
                    source_title="Test",
                    connector_credentials="creds",
                    knowledge_source_id="ks-1",
                    slug="test-src",
                    force_full=True,
                )
                mock_rag.delete_by_knowledge_source.assert_called_once()
                assert result["status"] == "ok"


def test_sync_s3_prefix_skips_unchanged():
    with patch.object(sync_s3_prefix, "retry", MagicMock()):
        mock_objects = [
            {"Key": "data/file1.txt", "Size": 100, "LastModified": datetime(2024, 1, 1, tzinfo=timezone.utc)},
        ]

        sid = str(__import__("uuid").uuid5(__import__("uuid").NAMESPACE_URL, "s3://mybucket/data/file1.txt"))

        with patch("app.services.s3._decrypt_credentials", return_value={"access_key": "ak"}), \
             patch("app.services.s3._get_s3_client"), \
             patch("app.services.s3._list_objects", return_value=mock_objects), \
             patch("app.services.s3.RAGService") as mock_rag_cls, \
             patch("app.services.s3.asyncio") as mock_asyncio, \
             patch("app.services.s3.EncryptionService"):

            mock_rag = mock_rag_cls.return_value
            mock_rag.get_source_metadata = AsyncMock(return_value={
                sid: {"source_modified_at": "2024-01-01T00:00:00+00:00", "chunk_count": 7}
            })
            mock_rag.ingest_document = AsyncMock()
            mock_rag.delete_by_source_id = AsyncMock()

            with patch("app.services.s3._update_source_status", new=AsyncMock()):
                mock_asyncio.run = lambda coro: _run_coro_sync(coro)

                result = sync_s3_prefix.run(
                    bucket="mybucket",
                    prefix="data/",
                    source_title="Test",
                    connector_credentials="creds",
                    knowledge_source_id="ks-1",
                    slug="test-src",
                )
                mock_rag.ingest_document.assert_not_called()
                assert result["status"] == "ok"


def test_sync_s3_prefix_exception_retries():
    mock_retry = MagicMock(side_effect=Exception("retry failed"))
    with patch.object(sync_s3_prefix, "retry", mock_retry):
        with patch("app.services.s3._decrypt_credentials", side_effect=Exception("decrypt failed")), \
             patch("app.services.s3.asyncio") as mock_asyncio, \
             patch("app.services.s3.EncryptionService"):
            mock_asyncio.run = lambda coro: _run_coro_sync(coro)
            with patch("app.services.s3._update_source_status", new=AsyncMock()):
                with pytest.raises(Exception):
                    sync_s3_prefix.run(
                        bucket="bucket",
                        prefix="prefix/",
                        source_title="Test",
                        connector_credentials="creds",
                    )
                mock_retry.assert_called_once()


def _run_coro_sync(coro):
    """Run an async coroutine synchronously for testing."""
    import asyncio
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()
