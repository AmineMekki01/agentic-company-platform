"""Tests for Google Drive sync service – mocked Google API."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.gdrive import (
    EXPORT_MIME_MAP,
    FILE_EXTENSION_MAP,
    SUPPORTED_MIME_TYPES,
    _download_file_content,
    _extract_text,
    _list_folder_files,
    sync_gdrive_folder,
)


def test_supported_mime_types_includes_pdf():
    assert "application/pdf" in SUPPORTED_MIME_TYPES


def test_export_mime_map_google_doc():
    assert EXPORT_MIME_MAP["application/vnd.google-apps.document"] == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def test_file_extension_map_pdf():
    assert FILE_EXTENSION_MAP["application/pdf"] == ".pdf"


def test_list_folder_files_recursive():
    mock_service = MagicMock()

    # First call: returns a folder and a file
    # Second call (recursive into folder): returns a file
    responses = [
        {"files": [
            {"id": "folder1", "name": "Subfolder", "mimeType": "application/vnd.google-apps.folder"},
            {"id": "file1", "name": "doc.pdf", "mimeType": "application/pdf", "modifiedTime": "2024-01-01T00:00:00Z", "webViewLink": "https://drive.google.com/file/d/file1"},
        ], "nextPageToken": None},
        {"files": [
            {"id": "file2", "name": "sheet.csv", "mimeType": "text/csv", "modifiedTime": "2024-01-02T00:00:00Z", "webViewLink": "https://drive.google.com/file/d/file2"},
        ], "nextPageToken": None},
    ]

    mock_files = MagicMock()
    mock_list = MagicMock()
    mock_list.execute.side_effect = responses
    mock_files.list.return_value = mock_list
    mock_service.files.return_value = mock_files

    files = _list_folder_files(mock_service, "root_folder")
    assert len(files) == 2
    file_ids = {f["id"] for f in files}
    assert file_ids == {"file1", "file2"}


def test_list_folder_files_skips_unsupported():
    mock_service = MagicMock()

    mock_files = MagicMock()
    mock_list = MagicMock()
    mock_list.execute.return_value = {
        "files": [
            {"id": "file1", "name": "doc.pdf", "mimeType": "application/pdf", "modifiedTime": "2024-01-01", "webViewLink": "url1"},
            {"id": "file2", "name": "video.mp4", "mimeType": "video/mp4", "modifiedTime": "2024-01-02", "webViewLink": "url2"},
        ],
        "nextPageToken": None,
    }
    mock_files.list.return_value = mock_list
    mock_service.files.return_value = mock_files

    files = _list_folder_files(mock_service, "root")
    assert len(files) == 1
    assert files[0]["id"] == "file1"


def test_download_file_content_regular():
    mock_service = MagicMock()
    mock_get = MagicMock()
    mock_get.execute.return_value = b"file bytes"
    mock_service.files().get_media.return_value = mock_get

    content, mime = _download_file_content(mock_service, "file1", "application/pdf")
    assert content == b"file bytes"
    assert mime == "application/pdf"


def test_download_file_content_google_doc_export():
    mock_service = MagicMock()
    mock_export = MagicMock()
    mock_export.execute.return_value = b"exported bytes"
    mock_service.files().export_media.return_value = mock_export

    content, mime = _download_file_content(mock_service, "file1", "application/vnd.google-apps.document")
    assert content == b"exported bytes"
    assert mime == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def test_extract_text_txt():
    with patch("app.services.gdrive.parse_upload", return_value="extracted text") as mock_parse:
        result = _extract_text(b"raw", "text/plain", "readme")
        assert result == "extracted text"
        mock_parse.assert_called_once_with(b"raw", "text/plain", "readme.txt")


def test_extract_text_csv():
    with patch("app.services.gdrive.parse_upload", return_value="csv data") as mock_parse:
        result = _extract_text(b"raw", "text/csv", "data")
        assert result == "csv data"
        mock_parse.assert_called_once_with(b"raw", "text/csv", "data.csv")


def _run_coro_sync(coro):
    import asyncio
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def test_sync_gdrive_folder_no_files():
    with patch.object(sync_gdrive_folder, "retry", MagicMock()):
        with patch("app.services.gdrive._get_drive_service"), \
             patch("app.services.gdrive._list_folder_files", return_value=[]), \
             patch("app.services.gdrive.asyncio") as mock_asyncio, \
             patch("app.services.gdrive._update_source_status", new=AsyncMock()):
            mock_asyncio.run = lambda coro: _run_coro_sync(coro)
            result = sync_gdrive_folder.run(
                folder_id="folder1", source_title="Test",
                connector_credentials="creds", slug="test-src",
            )
            assert result["status"] == "ok"
            assert result["files"] == 0


def test_sync_gdrive_folder_with_files():
    with patch.object(sync_gdrive_folder, "retry", MagicMock()):
        mock_files = [
            {"id": "f1", "name": "doc.pdf", "mimeType": "application/pdf", "modifiedTime": "2024-01-01T00:00:00Z", "webViewLink": "https://drive.google.com/f1"},
            {"id": "f2", "name": "notes.txt", "mimeType": "text/plain", "modifiedTime": "2024-01-02T00:00:00Z", "webViewLink": "https://drive.google.com/f2"},
        ]

        with patch("app.services.gdrive._get_drive_service"), \
             patch("app.services.gdrive._list_folder_files", return_value=mock_files), \
             patch("app.services.gdrive._download_file_content", return_value=(b"content", "application/pdf")), \
             patch("app.services.gdrive._extract_text", return_value="extracted text"), \
             patch("app.services.gdrive._detect_file_type", return_value="pdf"), \
             patch("app.services.gdrive.get_rag_service") as mock_get_rag, \
             patch("app.services.gdrive.asyncio") as mock_asyncio, \
             patch("app.services.gdrive._update_source_status", new=AsyncMock()):

            mock_rag = mock_get_rag.return_value
            mock_rag.get_source_metadata = AsyncMock(return_value={})
            mock_rag.ingest_document = AsyncMock(return_value=3)
            mock_rag.delete_by_source_id = AsyncMock()
            mock_rag.delete_by_knowledge_source = AsyncMock()

            mock_asyncio.run = lambda coro: _run_coro_sync(coro)

            result = sync_gdrive_folder.run(
                folder_id="folder1", source_title="Test",
                connector_credentials="creds", knowledge_source_id="ks-1",
                slug="test-src",
            )
            assert result["status"] == "ok"
            assert result["files"] == 2


def test_sync_gdrive_folder_force_full():
    with patch.object(sync_gdrive_folder, "retry", MagicMock()):
        mock_files = [
            {"id": "f1", "name": "doc.pdf", "mimeType": "application/pdf", "modifiedTime": "2024-01-01", "webViewLink": "url"},
        ]

        with patch("app.services.gdrive._get_drive_service"), \
             patch("app.services.gdrive._list_folder_files", return_value=mock_files), \
             patch("app.services.gdrive._download_file_content", return_value=(b"content", "application/pdf")), \
             patch("app.services.gdrive._extract_text", return_value="text"), \
             patch("app.services.gdrive._detect_file_type", return_value="pdf"), \
             patch("app.services.gdrive.get_rag_service") as mock_get_rag, \
             patch("app.services.gdrive.asyncio") as mock_asyncio, \
             patch("app.services.gdrive._update_source_status", new=AsyncMock()):

            mock_rag = mock_get_rag.return_value
            mock_rag.get_source_metadata = AsyncMock(return_value={})
            mock_rag.ingest_document = AsyncMock(return_value=2)
            mock_rag.delete_by_knowledge_source = AsyncMock()
            mock_rag.delete_by_source_id = AsyncMock()

            mock_asyncio.run = lambda coro: _run_coro_sync(coro)

            result = sync_gdrive_folder.run(
                folder_id="folder1", source_title="Test",
                connector_credentials="creds", knowledge_source_id="ks-1",
                slug="test-src", force_full=True,
            )
            mock_rag.delete_by_knowledge_source.assert_called_once()
            assert result["status"] == "ok"


def test_sync_gdrive_folder_exception_retries():
    mock_retry = MagicMock(side_effect=Exception("retry failed"))
    with patch.object(sync_gdrive_folder, "retry", mock_retry):
        with patch("app.services.gdrive._get_drive_service", side_effect=Exception("auth failed")), \
             patch("app.services.gdrive.asyncio") as mock_asyncio, \
             patch("app.services.gdrive._update_source_status", new=AsyncMock()):
            mock_asyncio.run = lambda coro: _run_coro_sync(coro)
            import pytest
            with pytest.raises(Exception):
                sync_gdrive_folder.run(
                    folder_id="folder1", source_title="Test",
                    connector_credentials="creds",
                )
            mock_retry.assert_called_once()
