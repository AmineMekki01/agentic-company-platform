"""Tests for RAG service – mocked Qdrant/OpenAI to avoid external deps."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.rag import (
    COLLECTION_NAME,
    DENSE_DIM,
    RAGService,
    RetrievedChunk,
    _extract_source_url,
)

pytestmark = pytest.mark.asyncio


def test_extract_source_url_found():
    payload = {"source_url": "https://example.com/doc.pdf"}
    assert _extract_source_url(payload) == "https://example.com/doc.pdf"


def test_extract_source_url_notion():
    payload = {"notion_page_url": "https://www.notion.so/abc123"}
    assert _extract_source_url(payload) == "https://www.notion.so/abc123"


def test_extract_source_url_none():
    payload = {"foo": "bar"}
    assert _extract_source_url(payload) is None


def test_extract_source_url_non_http():
    payload = {"url": "ftp://example.com/file"}
    assert _extract_source_url(payload) is None


def test_retrieved_chunk_defaults():
    chunk = RetrievedChunk(
        id="point-1",
        text="hello world",
        score=0.95,
        source_id="src-1",
        source_title="Doc 1",
        page=2,
        rank=1,
    )
    assert chunk.source_url is None


def test_rag_service_init_with_mocks():
    with patch("app.services.rag.AsyncQdrantClient"), \
         patch("app.services.rag.OpenAIEmbeddings"), \
         patch("app.services.rag.tiktoken.get_encoding", return_value=MagicMock()):
        svc = RAGService()
        assert svc.emb_model == "text-embedding-3-small"
        assert svc._sparse_model is None
        assert svc._sparse_available is None
        assert svc._local_reranker is None


async def test_rag_token_length():
    with patch("app.services.rag.AsyncQdrantClient"), \
         patch("app.services.rag.OpenAIEmbeddings"), \
         patch("app.services.rag.tiktoken.get_encoding") as mock_enc:
        mock_enc.return_value.encode.return_value = [1, 2, 3]
        svc = RAGService()
        assert svc._token_length("hello") == 3


async def test_rag_get_sparse_model_unavailable():
    with patch("app.services.rag.AsyncQdrantClient"), \
         patch("app.services.rag.OpenAIEmbeddings"), \
         patch("app.services.rag.tiktoken.get_encoding"):
        svc = RAGService()
        with patch("builtins.__import__", side_effect=ImportError("no fastembed")):
            result = svc._get_sparse_model()
        assert result is None
        assert svc._sparse_available is False


async def test_rag_embed_sparse_no_model():
    with patch("app.services.rag.AsyncQdrantClient"), \
         patch("app.services.rag.OpenAIEmbeddings"), \
         patch("app.services.rag.tiktoken.get_encoding"):
        svc = RAGService()
        svc._sparse_available = False
        assert svc._embed_sparse(["hello"]) is None


async def test_rag_ensure_collection_creates_new():
    with patch("app.services.rag.AsyncQdrantClient") as mock_qdrant_cls:
        client = mock_qdrant_cls.return_value
        client.collection_exists = AsyncMock(return_value=False)
        client.create_collection = AsyncMock()
        client.create_payload_index = AsyncMock()

        with patch("app.services.rag.OpenAIEmbeddings"), \
             patch("app.services.rag.tiktoken.get_encoding"):
            svc = RAGService()
            await svc.ensure_collection()
            client.create_collection.assert_called_once()
            call_kwargs = client.create_collection.call_args
            assert call_kwargs.kwargs["collection_name"] == COLLECTION_NAME


async def test_rag_ensure_collection_already_exists_with_dense():
    with patch("app.services.rag.AsyncQdrantClient") as mock_qdrant_cls:
        client = mock_qdrant_cls.return_value
        client.collection_exists = AsyncMock(return_value=True)

        mock_info = MagicMock()
        mock_info.config.params.vectors = {"dense": MagicMock()}
        client.get_collection = AsyncMock(return_value=mock_info)

        with patch("app.services.rag.OpenAIEmbeddings"), \
             patch("app.services.rag.tiktoken.get_encoding"):
            svc = RAGService()
            await svc.ensure_collection()
            client.create_collection.assert_not_called()


async def test_rag_ensure_collection_old_schema_recreates():
    with patch("app.services.rag.AsyncQdrantClient") as mock_qdrant_cls:
        client = mock_qdrant_cls.return_value
        client.collection_exists = AsyncMock(return_value=True)

        mock_info = MagicMock()
        mock_vectors = MagicMock()
        del mock_vectors.get
        mock_vectors.size = DENSE_DIM
        mock_info.config.params.vectors = mock_vectors
        client.get_collection = AsyncMock(return_value=mock_info)
        client.delete_collection = AsyncMock()
        client.create_collection = AsyncMock()
        client.create_payload_index = AsyncMock()

        with patch("app.services.rag.OpenAIEmbeddings"), \
             patch("app.services.rag.tiktoken.get_encoding"):
            svc = RAGService()
            await svc.ensure_collection()
            client.delete_collection.assert_called_once()
            client.create_collection.assert_called_once()


async def test_rag_ingest_document_empty_content():
    with patch("app.services.rag.AsyncQdrantClient"), \
         patch("app.services.rag.OpenAIEmbeddings"), \
         patch("app.services.rag.tiktoken.get_encoding"):
        svc = RAGService()
        import uuid as _uuid
        result = await svc.ingest_document(
            source_id=_uuid.uuid4(),
            title="Empty",
            content="",
            knowledge_source_id="ks-1",
        )
        assert result == 0


async def test_rag_ingest_document_with_content():
    with patch("app.services.rag.AsyncQdrantClient") as mock_qdrant_cls:
        client = mock_qdrant_cls.return_value
        client.upsert = AsyncMock()

        with patch("app.services.rag.OpenAIEmbeddings") as mock_emb_cls:
            emb = mock_emb_cls.return_value
            emb.aembed_documents = AsyncMock(return_value=[[0.1] * DENSE_DIM])

            with patch("app.services.rag.tiktoken.get_encoding"):
                svc = RAGService()
                svc._sparse_available = False

                import uuid as _uuid
                result = await svc.ingest_document(
                    source_id=_uuid.uuid4(),
                    title="Test Doc",
                    content="This is a test document with some content.",
                    knowledge_source_id="ks-1",
                    extra_payload={"file_name": "test.txt"},
                )
                assert result > 0
                client.upsert.assert_called_once()


async def test_rag_rerank_empty_candidates():
    with patch("app.services.rag.AsyncQdrantClient"), \
         patch("app.services.rag.OpenAIEmbeddings"), \
         patch("app.services.rag.tiktoken.get_encoding"):
        svc = RAGService()
        result = await svc._rerank("query", [], top_n=5)
        assert result == []


async def test_rag_rerank_fallback_raw_scores():
    with patch("app.services.rag.AsyncQdrantClient"), \
         patch("app.services.rag.OpenAIEmbeddings"), \
         patch("app.services.rag.tiktoken.get_encoding"):
        svc = RAGService()
        svc._get_local_reranker = lambda: None
        svc.cohere = None

        candidate = MagicMock()
        candidate.id = "point-1"
        candidate.score = 0.85
        candidate.payload = {"text": "hello", "source_id": "s1", "title": "Doc1", "page": 1}

        result = await svc._rerank("query", [candidate], top_n=5)
        assert len(result) == 1
        assert result[0].text == "hello"
        assert result[0].score == 0.85
        assert result[0].rank == 1


async def test_rag_delete_by_knowledge_source():
    with patch("app.services.rag.AsyncQdrantClient") as mock_qdrant_cls:
        client = mock_qdrant_cls.return_value
        client.scroll = AsyncMock(return_value=([], None))
        client.delete = AsyncMock()

        with patch("app.services.rag.OpenAIEmbeddings"), \
             patch("app.services.rag.tiktoken.get_encoding"):
            svc = RAGService()
            count = await svc.delete_by_knowledge_source("ks-1")
            assert count == 0


async def test_rag_delete_by_source_id():
    with patch("app.services.rag.AsyncQdrantClient") as mock_qdrant_cls:
        client = mock_qdrant_cls.return_value
        client.scroll = AsyncMock(return_value=([], None))
        client.delete = AsyncMock()

        with patch("app.services.rag.OpenAIEmbeddings"), \
             patch("app.services.rag.tiktoken.get_encoding"):
            svc = RAGService()
            count = await svc.delete_by_source_id("ks-1", "src-1")
            assert count == 0


async def test_rag_get_source_metadata():
    with patch("app.services.rag.AsyncQdrantClient") as mock_qdrant_cls:
        client = mock_qdrant_cls.return_value

        point = MagicMock()
        point.payload = {
            "source_id": "src-1",
            "title": "Doc 1",
            "source_modified_at": "2024-01-01T00:00:00",
        }
        client.scroll = AsyncMock(return_value=([point], None))

        with patch("app.services.rag.OpenAIEmbeddings"), \
             patch("app.services.rag.tiktoken.get_encoding"):
            svc = RAGService()
            meta = await svc.get_source_metadata("ks-1")
            assert "src-1" in meta
            assert meta["src-1"]["title"] == "Doc 1"
            assert meta["src-1"]["chunk_count"] == 1
