"""RAG pipeline: ingestion, hybrid search, reranking, citations.

Design
------
- Qdrant collection stores **dense** (OpenAI) and **sparse** (BM25-style) vectors.
- Retrieval = prefetch dense + sparse -> native Qdrant RRF fusion -> local / Cohere rerank.
- Each chunk carries metadata: source_id, title, page / chunk index so the
  assistant can cite sources.
"""

import asyncio
import logging
import uuid
from dataclasses import dataclass
from typing import Any, Callable, TypeVar

import cohere
import tiktoken
from langchain_openai import OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from qdrant_client import AsyncQdrantClient, models

from app.core.config import settings

T = TypeVar("T")

_QDRANT_MAX_RETRIES = 3
_QDRANT_BASE_DELAY = 0.5


async def _qdrant_retry(
    func: Callable[..., Any],
    *args: Any,
    max_retries: int = _QDRANT_MAX_RETRIES,
    base_delay: float = _QDRANT_BASE_DELAY,
    **kwargs: Any,
) -> Any:
    for attempt in range(max_retries):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            if attempt == max_retries - 1:
                raise
            delay = base_delay * (2 ** attempt)
            logger.warning(
                "Qdrant op failed (attempt %d/%d): %s, retrying in %.1fs",
                attempt + 1, max_retries, e, delay,
            )
            await asyncio.sleep(delay)



def _get_tokenizer() -> tiktoken.Encoding:
    """Return the tiktoken encoding for the current embedding model."""
    return tiktoken.get_encoding("cl100k_base")

logger = logging.getLogger(__name__)

COLLECTION_NAME = "company_knowledge"
DENSE_DIM = 1536
TOP_K = 10
RERANK_TOP_K = 5


def _extract_source_url(payload: dict[str, Any]) -> str | None:
    """
    Try common URL keys in Qdrant payload to find an original document link.
    
    Args:
        payload: Qdrant payload dictionary
        
    Returns:
        Extracted source URL or None
    """
    for key in ("source_url", "notion_page_url", "url", "s3_url", "sharepoint_url", "gdrive_file_url"):
        val = payload.get(key)
        if val and isinstance(val, str) and val.startswith("http"):
            return val
    return None


@dataclass
class RetrievedChunk:
    """
    Data class representing a retrieved chunk from the RAG system.
    
    Attributes:
        id: Unique identifier for the chunk
        text: The chunk text content
        score: Retrieval score (higher is better)
        source_id: Source identifier (e.g., document ID)
        source_title: Title of the source document
        page: Page number where the chunk appears (if applicable)
        rank: Rank of the chunk in the retrieval results
        source_url: URL of the original source document (if available)
    """
    id: str
    text: str
    score: float
    source_id: str
    source_title: str
    page: int | None
    rank: int
    source_url: str | None = None


class RAGService:
    def __init__(self) -> None:
        self.qdrant = AsyncQdrantClient(
            url=settings.qdrant_url, check_compatibility=False
        )
        self.emb_model = "text-embedding-3-small"
        self.embeddings = OpenAIEmbeddings(
            model=self.emb_model,
            api_key=settings.openai_api_key or None,
            chunk_size=100,
        )
        self._tokenizer = _get_tokenizer()
        self._sparse_model: Any | None = None
        self._sparse_available: bool | None = None
        self._local_reranker: Any | None = None
        self.cohere = (
            cohere.AsyncClientV2(settings.cohere_api_key)
            if settings.cohere_api_key
            else None
        )

    def _token_length(self, text: str) -> int:
        """Count tokens using the model-aware tokenizer."""
        return len(self._tokenizer.encode(text, disallowed_special=()))

    async def close(self) -> None:
        """Close underlying client connections."""
        try:
            await self.qdrant.close()
        except Exception:
            logger.warning("Error closing Qdrant client", exc_info=True)
        if self.cohere is not None:
            try:
                await self.cohere.close()
            except Exception:
                logger.warning("Error closing Cohere client", exc_info=True)

    def _get_local_reranker(self) -> Any | None:
        """Lazily load a local cross-encoder reranker if sentence-transformers is available."""
        if self._local_reranker is not None:
            return self._local_reranker
        try:
            from sentence_transformers import CrossEncoder
            self._local_reranker = CrossEncoder("BAAI/bge-reranker-v2-m3")
            logger.info("Loaded local reranker: BAAI/bge-reranker-v2-m3")
        except Exception:
            logger.debug("sentence-transformers not available for local reranking")
            self._local_reranker = False
        return self._local_reranker if self._local_reranker is not False else None

    def _get_sparse_model(self) -> Any | None:
        """Lazily load the fastembed Qdrant/bm25 sparse embedding model."""
        if self._sparse_available is not None:
            return self._sparse_model
        try:
            from fastembed import SparseTextEmbedding

            self._sparse_model = SparseTextEmbedding(model_name="Qdrant/bm25")
            self._sparse_available = True
            logger.info("Loaded fastembed Qdrant/bm25 sparse model")
        except Exception:
            logger.warning(
                "fastembed not available; sparse embeddings disabled. "
                "Install with: pip install fastembed"
            )
            self._sparse_available = False
        return self._sparse_model

    def _embed_sparse(self, texts: list[str]) -> list[models.SparseVector] | None:
        """Embed texts into sparse vectors using fastembed Qdrant/bm25.

        Returns None when the sparse model is unavailable, allowing callers
        to fall back to dense-only mode.
        """
        model = self._get_sparse_model()
        if model is None:
            return None
        embeddings = list(model.embed(texts))
        return [
            models.SparseVector(
                indices=emb.indices.tolist(),
                values=emb.values.tolist(),
            )
            for emb in embeddings
        ]

    async def ensure_collection(self) -> None:
        """
        Ensure the Qdrant collection exists with dense and sparse vectors.

        Named vectors:
        - dense: semantic embeddings (OpenAI text-embedding-3-small)
        - sparse: keyword BM25-style sparse embeddings via fastembed Qdrant/bm25

        If the collection exists but was created with an old unnamed vector
        schema, it is dropped and recreated.
        """
        exists = await _qdrant_retry(self.qdrant.collection_exists, COLLECTION_NAME)
        if exists:
            info = await _qdrant_retry(self.qdrant.get_collection, COLLECTION_NAME)
            vectors = info.config.params.vectors

            if vectors is not None and hasattr(vectors, "get") and vectors.get("dense"):
                return
            if (
                vectors is not None
                and not hasattr(vectors, "get")
                and getattr(vectors, "size", None) == DENSE_DIM
            ):

                logger.warning(
                    "Collection %s has an old unnamed vector schema. Recreating.",
                    COLLECTION_NAME,
                )
                await _qdrant_retry(self.qdrant.delete_collection, COLLECTION_NAME)
            else:
                logger.warning(
                    "Collection %s schema mismatch. Recreating.", COLLECTION_NAME
                )
                await _qdrant_retry(self.qdrant.delete_collection, COLLECTION_NAME)

        await _qdrant_retry(
            self.qdrant.create_collection,
            collection_name=COLLECTION_NAME,
            vectors_config={
                "dense": models.VectorParams(
                    size=DENSE_DIM,
                    distance=models.Distance.COSINE,
                )
            },
            sparse_vectors_config={
                "sparse": models.SparseVectorParams(
                    index=models.SparseIndexParams(),
                    modifier=models.Modifier.IDF,
                )
            },
        )
        logger.info("Created Qdrant collection %s", COLLECTION_NAME)

    async def ingest_document(
        self,
        source_id: uuid.UUID,
        title: str,
        content: str,
        knowledge_source_id: str,
        extra_payload: dict[str, Any] | None = None,
    ) -> int:
        """
        Chunk text, embed, upsert. Returns number of chunks.
        
        Args:
            source_id: Unique identifier for the source document
            title: Title of the source document
            content: Text content to ingest
            knowledge_source_id: UUID of the KnowledgeSource this document belongs to.
                Stored in Qdrant payload as "knowledge_source_id" for retrieval filtering.
            extra_payload: Additional metadata to store with each chunk
            
        Returns:
            Number of chunks ingested
        """
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=512,
            chunk_overlap=64,
            length_function=self._token_length,
            separators=["\n\n", "\n", ". ", " ", ""],
        )
        docs = splitter.create_documents([content])
        if not docs:
            return 0

        texts = [d.page_content for d in docs]
        dense_vectors = await self.embeddings.aembed_documents(texts)
        sparse_vectors = self._embed_sparse(texts)

        points = []
        for i, doc in enumerate(docs):
            payload: dict[str, Any] = {
                "text": doc.page_content,
                "source_id": str(source_id),
                "title": title,
                "chunk_index": i,
            }
            if extra_payload:
                payload.update(extra_payload)
            payload["knowledge_source_id"] = knowledge_source_id
            vector: dict[str, Any] = {"dense": dense_vectors[i]}
            if sparse_vectors is not None:
                vector["sparse"] = sparse_vectors[i]
            points.append(
                models.PointStruct(
                    id=str(uuid.uuid4()),
                    vector=vector,
                    payload=payload,
                )
            )

        await _qdrant_retry(self.qdrant.upsert, collection_name=COLLECTION_NAME, points=points)
        return len(points)

    async def _rerank(
        self, query: str, candidates: list[Any], top_n: int = RERANK_TOP_K
    ) -> list[RetrievedChunk]:
        """Rerank candidates: local cross-encoder first, then Cohere, then raw scores."""
        if not candidates:
            return []

        local = self._get_local_reranker()
        if local is not None:
            texts = [p.payload["text"] for p in candidates if p.payload]
            pairs = [(query, t) for t in texts]
            scores = local.predict(pairs)
            scored = sorted(
                zip(candidates, scores), key=lambda x: x[1], reverse=True
            )
            return [
                RetrievedChunk(
                    id=c.id,
                    text=c.payload["text"],
                    score=float(s),
                    source_id=c.payload.get("source_id", ""),
                    source_title=c.payload.get("title", ""),
                    page=c.payload.get("page"),
                    rank=i + 1,
                    source_url=_extract_source_url(c.payload or {}),
                )
                for i, (c, s) in enumerate(scored[:top_n])
            ]

        if self.cohere is not None:
            texts = [p.payload["text"] for p in candidates if p.payload]
            try:
                rerank_resp = await self.cohere.rerank(
                    model="rerank-v3.5",
                    query=query,
                    documents=texts,
                    top_n=top_n,
                )
                return [
                    RetrievedChunk(
                        id=candidates[r.index].id,
                        text=texts[r.index],
                        score=r.relevance_score,
                        source_id=candidates[r.index].payload.get("source_id", ""),
                        source_title=candidates[r.index].payload.get("title", ""),
                        page=candidates[r.index].payload.get("page"),
                        rank=i + 1,
                        source_url=_extract_source_url(
                            candidates[r.index].payload or {}
                        ),
                    )
                    for i, r in enumerate(rerank_resp.results)
                ]
            except Exception:
                logger.exception("Cohere rerank failed, falling back to RRF scores")

        return [
            RetrievedChunk(
                id=p.id,
                text=p.payload["text"],
                score=p.score,
                source_id=p.payload.get("source_id", ""),
                source_title=p.payload.get("title", ""),
                page=p.payload.get("page"),
                rank=i + 1,
                source_url=_extract_source_url(p.payload or {}),
            )
            for i, p in enumerate(candidates[:top_n])
        ]

    async def retrieve(
        self, query: str, source_ids: list[str] | None = None, top_k: int = 5
    ) -> list[RetrievedChunk]:
        """
        Hybrid search -> native Qdrant RRF fusion -> rerank.

        Uses Qdrant's built-in prefetch and reciprocal rank fusion, then reranks
        the fused candidates with a local cross-encoder if available, otherwise
        Cohere. If no reranker is configured, returns the RRF-ranked results.
        """
        await self.ensure_collection()

        prefetch_limit = top_k * 3
        rrf_limit = top_k * 2
        logger.warning("RAG retrieve query=%r source_ids=%s top_k=%d (prefetch=%d rrf=%d)", query, source_ids, top_k, prefetch_limit, rrf_limit)

        try:
            dense_query = await self.embeddings.aembed_query(query)
            sparse_query = self._embed_sparse([query])
            sparse_available = sparse_query is not None
            if not sparse_available:
                logger.warning("RAG retrieve: sparse model unavailable, using dense-only search")

            qdrant_filter = None
            if source_ids:
                qdrant_filter = models.Filter(
                    must=[
                        models.FieldCondition(
                            key="knowledge_source_id",
                            match=models.MatchAny(any=source_ids),
                        )
                    ]
                )
                logger.warning("RAG filter: knowledge_source_id IN %s", source_ids)
            else:
                logger.warning("RAG filter: NONE (searching all sources)")

            if sparse_available:
                resp = await _qdrant_retry(
                    self.qdrant.query_points,
                    collection_name=COLLECTION_NAME,
                    prefetch=[
                        models.Prefetch(
                            query=dense_query,
                            using="dense",
                            limit=prefetch_limit,
                            filter=qdrant_filter,
                        ),
                        models.Prefetch(
                            query=sparse_query[0],
                            using="sparse",
                            limit=prefetch_limit,
                            filter=qdrant_filter,
                        ),
                    ],
                    query=models.FusionQuery(fusion=models.Fusion.RRF),
                    limit=rrf_limit,
                    with_payload=True,
                )
            else:
                resp = await _qdrant_retry(
                    self.qdrant.query_points,
                    collection_name=COLLECTION_NAME,
                    prefetch=[
                        models.Prefetch(
                            query=dense_query,
                            using="dense",
                            limit=prefetch_limit,
                            filter=qdrant_filter,
                        ),
                    ],
                    limit=rrf_limit,
                    with_payload=True,
                )
        except Exception:
            logger.exception("Qdrant retrieve failed after retries, returning empty results")
            return []

        raw_unique: dict[str, str] = {}
        for p in resp.points:
            if p.payload:
                sid = p.payload.get("source_id", "unknown")
                raw_unique[sid] = p.payload.get("title", "untitled")
        logger.warning(
            "RAG Qdrant raw: %d points from sources: %s",
            len(resp.points),
            ", ".join(f"{sid[:8]}...={title}" for sid, title in sorted(raw_unique.items())) if raw_unique else "none",
        )

        result = await self._rerank(query, resp.points, top_n=top_k)
        final_unique: dict[str, str] = {}
        for c in result:
            final_unique[c.source_id] = c.source_title
        logger.warning(
            "RAG reranked final: %d chunks from sources: %s",
            len(result),
            ", ".join(f"{sid[:8]}...={title}" for sid, title in sorted(final_unique.items())) if final_unique else "none",
        )
        return result

    async def delete_by_knowledge_source(self, knowledge_source_id: str) -> int:
        """
        Delete all chunks tagged with a knowledge_source_id. Returns deleted count.
        
        Args:
            knowledge_source_id: The knowledge source ID to delete
            
        Returns:
            Number of chunks deleted
        """
        total_deleted = 0
        while True:
            points, next_offset = await _qdrant_retry(
                self.qdrant.scroll,
                collection_name=COLLECTION_NAME,
                scroll_filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="knowledge_source_id",
                            match=models.MatchValue(value=knowledge_source_id),
                        )
                    ]
                ),
                limit=250,
                offset=total_deleted,
                with_payload=False,
            )
            if not points:
                break
            ids = [p.id for p in points]
            await _qdrant_retry(
                self.qdrant.delete,
                collection_name=COLLECTION_NAME,
                points_selector=models.PointIdsList(points=ids),
            )
            total_deleted += len(ids)
            if not next_offset:
                break
        logger.info("Deleted %d chunks for knowledge_source_id=%s", total_deleted, knowledge_source_id)
        return total_deleted

    async def delete_by_source_id(self, knowledge_source_id: str, source_id: str) -> int:
        """
        Delete all chunks for a single document (source_id) within a knowledge source.

        Args:
            knowledge_source_id: The knowledge source ID the document belongs to.
            source_id: The source_id of the document to delete.

        Returns:
            Number of chunks deleted.
        """
        total_deleted = 0
        while True:
            points, next_offset = await _qdrant_retry(
                self.qdrant.scroll,
                collection_name=COLLECTION_NAME,
                scroll_filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="knowledge_source_id",
                            match=models.MatchValue(value=knowledge_source_id),
                        ),
                        models.FieldCondition(
                            key="source_id",
                            match=models.MatchValue(value=source_id),
                        ),
                    ]
                ),
                limit=250,
                offset=total_deleted,
                with_payload=False,
            )
            if not points:
                break
            ids = [p.id for p in points]
            await _qdrant_retry(
                self.qdrant.delete,
                collection_name=COLLECTION_NAME,
                points_selector=models.PointIdsList(points=ids),
            )
            total_deleted += len(ids)
            if not next_offset:
                break
        logger.info("Deleted %d chunks for source_id=%s (ks=%s)", total_deleted, source_id, knowledge_source_id)
        return total_deleted

    async def get_source_metadata(self, knowledge_source_id: str) -> dict[str, dict[str, Any]]:
        """
        Get metadata for all documents in a knowledge source.

        Returns a mapping of source_id -> {source_modified_at, chunk_count, title}
        for incremental sync comparisons.
        """
        result: dict[str, dict[str, Any]] = {}
        offset = 0
        while True:
            points, next_offset = await _qdrant_retry(
                self.qdrant.scroll,
                collection_name=COLLECTION_NAME,
                scroll_filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="knowledge_source_id",
                            match=models.MatchValue(value=knowledge_source_id),
                        )
                    ]
                ),
                limit=250,
                offset=offset,
                with_payload=True,
                with_vectors=False,
            )
            for p in points:
                payload = p.payload or {}
                sid = payload.get("source_id")
                if sid and sid not in result:
                    result[sid] = {
                        "source_modified_at": payload.get("source_modified_at"),
                        "title": payload.get("title", ""),
                        "chunk_count": 0,
                    }
                if sid:
                    result[sid]["chunk_count"] += 1
            if not next_offset:
                break
            offset += len(points)
        return result


_rag_instance: RAGService | None = None


def get_rag_service() -> RAGService:
    """Return the singleton RAGService instance, creating it on first call."""
    global _rag_instance
    if _rag_instance is None:
        _rag_instance = RAGService()
    return _rag_instance


def _reset_rag_service() -> None:
    """Clear the singleton instance. Intended for test isolation only."""
    global _rag_instance
    _rag_instance = None