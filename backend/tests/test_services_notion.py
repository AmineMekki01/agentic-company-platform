"""Tests for Notion sync service – mocked Notion API."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.notion import (
    _extract_text_from_block,
    _find_child_pages,
    _get_token_from_connector,
    _resolve_token,
    fetch_database_pages,
    fetch_page_content,
    sync_notion_database,
    sync_notion_page,
    _fetch_page_metadata,
)


def test_extract_text_from_paragraph():
    block = {
        "type": "paragraph",
        "paragraph": {
            "rich_text": [{"plain_text": "Hello world"}],
        },
    }
    assert _extract_text_from_block(block) == "Hello world"


def test_extract_text_from_block_with_children():
    block = {
        "type": "paragraph",
        "paragraph": {
            "rich_text": [{"plain_text": "Parent"}],
            "children": [
                {
                    "type": "paragraph",
                    "paragraph": {"rich_text": [{"plain_text": "Child"}]},
                },
            ],
        },
    }
    result = _extract_text_from_block(block)
    assert "Parent" in result
    assert "Child" in result


def test_extract_text_from_empty_block():
    block = {"type": "heading_1", "heading_1": {"rich_text": []}}
    assert _extract_text_from_block(block) == ""


def test_get_token_from_connector_json():
    from cryptography.fernet import Fernet
    from app.core.config import settings
    old_key = settings.fernet_key
    settings.fernet_key = Fernet.generate_key().decode()
    try:
        from app.core.encryption import EncryptionService
        crypto = EncryptionService()
        creds = {"token": "secret_token"}
        encrypted = crypto.encrypt(json.dumps(creds))
        assert _get_token_from_connector(encrypted) == "secret_token"
    finally:
        settings.fernet_key = old_key


def test_get_token_from_connector_api_key():
    from cryptography.fernet import Fernet
    from app.core.config import settings
    old_key = settings.fernet_key
    settings.fernet_key = Fernet.generate_key().decode()
    try:
        from app.core.encryption import EncryptionService
        crypto = EncryptionService()
        creds = {"api_key": "ak_value"}
        encrypted = crypto.encrypt(json.dumps(creds))
        assert _get_token_from_connector(encrypted) == "ak_value"
    finally:
        settings.fernet_key = old_key


def test_get_token_from_connector_integration_token():
    from cryptography.fernet import Fernet
    from app.core.config import settings
    old_key = settings.fernet_key
    settings.fernet_key = Fernet.generate_key().decode()
    try:
        from app.core.encryption import EncryptionService
        crypto = EncryptionService()
        creds = {"integration_token": "it_value"}
        encrypted = crypto.encrypt(json.dumps(creds))
        assert _get_token_from_connector(encrypted) == "it_value"
    finally:
        settings.fernet_key = old_key


def test_get_token_from_connector_literal_eval():
    from cryptography.fernet import Fernet
    from app.core.config import settings
    old_key = settings.fernet_key
    settings.fernet_key = Fernet.generate_key().decode()
    try:
        from app.core.encryption import EncryptionService
        crypto = EncryptionService()
        creds_str = "{'token': 'tok_from_literal'}"
        encrypted = crypto.encrypt(creds_str)
        assert _get_token_from_connector(encrypted) == "tok_from_literal"
    finally:
        settings.fernet_key = old_key


def test_resolve_token_from_credentials():
    from cryptography.fernet import Fernet
    from app.core.config import settings
    old_key = settings.fernet_key
    settings.fernet_key = Fernet.generate_key().decode()
    try:
        from app.core.encryption import EncryptionService
        crypto = EncryptionService()
        creds = {"token": "my_token"}
        encrypted = crypto.encrypt(json.dumps(creds))
        assert _resolve_token(encrypted) == "my_token"
    finally:
        settings.fernet_key = old_key


def test_resolve_token_no_credentials_no_settings():
    with patch("app.services.notion.settings") as mock_settings:
        mock_settings.notion_token = None
        with pytest.raises(RuntimeError, match="No Notion token"):
            _resolve_token(None)


def test_resolve_token_from_settings():
    with patch("app.services.notion.settings") as mock_settings:
        mock_settings.notion_token = "settings_token"
        assert _resolve_token(None) == "settings_token"


def test_fetch_database_pages():
    with patch("app.services.notion._notion_client") as mock_client_fn:
        mock_client = MagicMock()
        mock_resp1 = {"results": [{"id": "p1"}, {"id": "p2"}], "next_cursor": "cursor1"}
        mock_resp2 = {"results": [{"id": "p3"}], "next_cursor": None}
        mock_client.databases.query.side_effect = [mock_resp1, mock_resp2]
        mock_client_fn.return_value = mock_client

        pages = fetch_database_pages("db1", "token")
        assert len(pages) == 3
        assert pages[0]["id"] == "p1"
        assert pages[2]["id"] == "p3"


def test_fetch_page_content():
    with patch("app.services.notion._notion_client") as mock_client_fn:
        mock_client = MagicMock()
        mock_resp = {
            "results": [
                {"type": "paragraph", "paragraph": {"rich_text": [{"plain_text": "Hello"}]}},
                {"type": "heading_1", "heading_1": {"rich_text": [{"plain_text": "Title"}]}},
            ],
            "next_cursor": None,
        }
        mock_client.blocks.children.list.return_value = mock_resp
        mock_client_fn.return_value = mock_client

        text = fetch_page_content("page1", "token")
        assert "Hello" in text
        assert "Title" in text


def test_find_child_pages():
    with patch("app.services.notion._notion_client") as mock_client_fn:
        mock_client = MagicMock()
        mock_resp = {
            "results": [
                {"type": "child_page", "id": "child1", "child_page": {"title": "Child Page"}, "has_children": False},
                {"type": "paragraph", "paragraph": {"rich_text": []}, "has_children": False},
            ],
            "next_cursor": None,
        }
        mock_client.blocks.children.list.return_value = mock_resp
        mock_client_fn.return_value = mock_client

        children = _find_child_pages("parent1", "token")
        assert len(children) == 1
        assert children[0]["id"] == "child1"
        assert children[0]["title"] == "Child Page"


def test_fetch_page_metadata_with_properties():
    with patch("app.services.notion._notion_client") as mock_client_fn:
        mock_client = MagicMock()
        mock_client.pages.retrieve.return_value = {
            "last_edited_time": "2024-01-01T00:00:00Z",
            "properties": {
                "title": {"title": [{"plain_text": "My Page"}]}
            },
        }
        mock_client_fn.return_value = mock_client

        meta = _fetch_page_metadata("page1", "token")
        assert meta["last_edited_time"] == "2024-01-01T00:00:00Z"
        assert meta["title"] == "My Page"


def test_fetch_page_metadata_with_url():
    with patch("app.services.notion._notion_client") as mock_client_fn:
        mock_client = MagicMock()
        mock_client.pages.retrieve.return_value = {
            "last_edited_time": "2024-01-01",
            "url": "https://www.notion.so/My-Page-abc123",
        }
        mock_client_fn.return_value = mock_client

        meta = _fetch_page_metadata("page1", "token")
        assert meta["title"] == "My-Page-abc123"


def test_fetch_page_metadata_exception():
    with patch("app.services.notion._notion_client") as mock_client_fn:
        mock_client = MagicMock()
        mock_client.pages.retrieve.side_effect = Exception("API error")
        mock_client_fn.return_value = mock_client

        meta = _fetch_page_metadata("page1", "token")
        assert meta["last_edited_time"] == ""
        assert meta["title"] == "page1"


def _run_coro_sync(coro):
    import asyncio
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def test_sync_notion_database_no_pages():
    with patch.object(sync_notion_database, "retry", MagicMock()):
        with patch("app.services.notion._resolve_token", return_value="tok"), \
             patch("app.services.notion.fetch_database_pages", return_value=[]), \
             patch("app.services.notion.RAGService") as mock_rag_cls, \
             patch("app.services.notion.asyncio") as mock_asyncio, \
             patch("app.services.notion._update_source_status", new=AsyncMock()):
            mock_rag = mock_rag_cls.return_value
            mock_rag.get_source_metadata = AsyncMock(return_value={})
            mock_rag.delete_by_source_id = AsyncMock()
            mock_asyncio.run = lambda coro: _run_coro_sync(coro)
            result = sync_notion_database.run(
                database_id="db1", source_title="Test",
                connector_credentials="creds", slug="test-src",
            )
            assert result["status"] == "ok"
            assert result["pages"] == 0


def test_sync_notion_database_with_pages():
    with patch.object(sync_notion_database, "retry", MagicMock()):
        page_id = "abc123def45678901234567890123456"
        mock_pages = [
            {"id": page_id, "last_edited_time": "2024-01-01T00:00:00Z",
             "properties": {"Name": {"title": [{"plain_text": "Page 1"}]}}},
        ]

        with patch("app.services.notion._resolve_token", return_value="tok"), \
             patch("app.services.notion.fetch_database_pages", return_value=mock_pages), \
             patch("app.services.notion.fetch_page_content", return_value="page content"), \
             patch("app.services.notion.RAGService") as mock_rag_cls, \
             patch("app.services.notion.asyncio") as mock_asyncio, \
             patch("app.services.notion._update_source_status", new=AsyncMock()):

            mock_rag = mock_rag_cls.return_value
            mock_rag.get_source_metadata = AsyncMock(return_value={})
            mock_rag.ingest_document = AsyncMock(return_value=4)
            mock_rag.delete_by_source_id = AsyncMock()
            mock_rag.delete_by_knowledge_source = AsyncMock()

            mock_asyncio.run = lambda coro: _run_coro_sync(coro)

            result = sync_notion_database.run(
                database_id="db1", source_title="Test",
                connector_credentials="creds", knowledge_source_id="ks-1",
                slug="test-src",
            )
            assert result["status"] == "ok"
            assert result["pages"] == 1
            mock_rag.ingest_document.assert_called_once()


def test_sync_notion_database_force_full():
    with patch.object(sync_notion_database, "retry", MagicMock()):
        page_id = "abc123def45678901234567890123456"
        mock_pages = [{"id": page_id, "last_edited_time": "2024-01-01", "properties": {"Name": {"title": [{"plain_text": "P1"}]}}}]

        with patch("app.services.notion._resolve_token", return_value="tok"), \
             patch("app.services.notion.fetch_database_pages", return_value=mock_pages), \
             patch("app.services.notion.fetch_page_content", return_value="content"), \
             patch("app.services.notion.RAGService") as mock_rag_cls, \
             patch("app.services.notion.asyncio") as mock_asyncio, \
             patch("app.services.notion._update_source_status", new=AsyncMock()):

            mock_rag = mock_rag_cls.return_value
            mock_rag.get_source_metadata = AsyncMock(return_value={})
            mock_rag.ingest_document = AsyncMock(return_value=2)
            mock_rag.delete_by_knowledge_source = AsyncMock()
            mock_rag.delete_by_source_id = AsyncMock()

            mock_asyncio.run = lambda coro: _run_coro_sync(coro)

            result = sync_notion_database.run(
                database_id="db1", source_title="Test",
                connector_credentials="creds", knowledge_source_id="ks-1",
                slug="test-src", force_full=True,
            )
            mock_rag.delete_by_knowledge_source.assert_called_once()
            assert result["status"] == "ok"


def test_sync_notion_database_exception_retries():
    mock_retry = MagicMock(side_effect=Exception("retry failed"))
    with patch.object(sync_notion_database, "retry", mock_retry):
        with patch("app.services.notion._resolve_token", side_effect=Exception("token error")), \
             patch("app.services.notion.asyncio") as mock_asyncio, \
             patch("app.services.notion._update_source_status", new=AsyncMock()):
            mock_asyncio.run = lambda coro: _run_coro_sync(coro)
            with pytest.raises(Exception):
                sync_notion_database.run(
                    database_id="db1", source_title="Test",
                    connector_credentials="creds",
                )
            mock_retry.assert_called_once()


def test_sync_notion_page_basic():
    with patch.object(sync_notion_page, "retry", MagicMock()):
        page_id = "abc123def45678901234567890123456"

        with patch("app.services.notion._resolve_token", return_value="tok"), \
             patch("app.services.notion._fetch_page_metadata", return_value={"last_edited_time": "2024-01-01", "title": "My Page"}), \
             patch("app.services.notion.fetch_page_content", return_value="page text"), \
             patch("app.services.notion._find_child_pages", return_value=[]), \
             patch("app.services.notion.RAGService") as mock_rag_cls, \
             patch("app.services.notion.asyncio") as mock_asyncio, \
             patch("app.services.notion._update_source_status", new=AsyncMock()):

            mock_rag = mock_rag_cls.return_value
            mock_rag.get_source_metadata = AsyncMock(return_value={})
            mock_rag.ingest_document = AsyncMock(return_value=3)
            mock_rag.delete_by_source_id = AsyncMock()
            mock_rag.delete_by_knowledge_source = AsyncMock()

            mock_asyncio.run = lambda coro: _run_coro_sync(coro)

            result = sync_notion_page.run(
                page_id=page_id, page_title="My Page",
                source_title="Test", connector_credentials="creds",
                knowledge_source_id="ks-1", slug="test-src",
            )
            assert result["status"] == "ok"
            mock_rag.ingest_document.assert_called_once()


def test_sync_notion_page_with_children():
    with patch.object(sync_notion_page, "retry", MagicMock()):
        page_id = "abc123def45678901234567890123456"
        child_id = "cdef1234567890abcdef1234567890ab"

        with patch("app.services.notion._resolve_token", return_value="tok"), \
             patch("app.services.notion._fetch_page_metadata", return_value={"last_edited_time": "2024-01-01", "title": "Page"}), \
             patch("app.services.notion.fetch_page_content", return_value="text"), \
             patch("app.services.notion._find_child_pages", return_value=[{"id": child_id, "title": "Child"}]), \
             patch("app.services.notion.RAGService") as mock_rag_cls, \
             patch("app.services.notion.asyncio") as mock_asyncio, \
             patch("app.services.notion._update_source_status", new=AsyncMock()):

            mock_rag = mock_rag_cls.return_value
            mock_rag.get_source_metadata = AsyncMock(return_value={})
            mock_rag.ingest_document = AsyncMock(return_value=2)
            mock_rag.delete_by_source_id = AsyncMock()
            mock_rag.delete_by_knowledge_source = AsyncMock()

            mock_asyncio.run = lambda coro: _run_coro_sync(coro)

            result = sync_notion_page.run(
                page_id=page_id, page_title="Page",
                source_title="Test", connector_credentials="creds",
                knowledge_source_id="ks-1", slug="test-src",
            )
            assert result["status"] == "ok"
            assert mock_rag.ingest_document.call_count == 2


def test_sync_notion_page_exception_retries():
    mock_retry = MagicMock(side_effect=Exception("retry failed"))
    with patch.object(sync_notion_page, "retry", mock_retry):
        with patch("app.services.notion._resolve_token", side_effect=Exception("no token")), \
             patch("app.services.notion.asyncio") as mock_asyncio, \
             patch("app.services.notion._update_source_status", new=AsyncMock()):
            mock_asyncio.run = lambda coro: _run_coro_sync(coro)
            with pytest.raises(Exception):
                sync_notion_page.run(
                    page_id="page1", page_title="Title",
                    source_title="Test", connector_credentials="creds",
                )
            mock_retry.assert_called_once()
