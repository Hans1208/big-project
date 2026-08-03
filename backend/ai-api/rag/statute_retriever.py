"""Retrieve statute articles from the local vector index."""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from rag.config import (
    CHROMA_DB_DIR,
    LEGAL_STATUTES_COLLECTION_NAME,
)
from rag.embedding_service import EmbeddingService
from rag.vector_store import ChromaVectorStore


MINIMUM_CANDIDATE_COUNT = 10
CANDIDATE_MULTIPLIER = 5


class StatuteRetriever:
    """Search statute chunks and return unique articles."""

    def __init__(
        self,
        embedding_service: Any | None = None,
        vector_store: Any | None = None,
    ) -> None:
        if embedding_service is None:
            embedding_service = EmbeddingService()

        if vector_store is None:
            vector_store = ChromaVectorStore(
                persist_directory=CHROMA_DB_DIR,
                collection_name=(
                    LEGAL_STATUTES_COLLECTION_NAME
                ),
            )

        self.embedding_service = embedding_service
        self.vector_store = vector_store

    def retrieve(
        self,
        query: str,
        law_id: str | None = None,
        top_k: int = 5,
    ) -> list[dict[str, Any]]:
        """Return unique statute articles by similarity."""
        clean_query = query.strip()

        if not clean_query:
            raise ValueError(
                "query must not be empty."
            )

        if top_k < 1:
            raise ValueError(
                "top_k must be at least 1."
            )

        clean_law_id = (
            law_id.strip()
            if law_id is not None
            else ""
        )

        where_filter = (
            {
                "law_id": clean_law_id,
            }
            if clean_law_id
            else None
        )

        query_embedding = (
            self.embedding_service.embed_query(
                clean_query
            )
        )

        candidate_count = max(
            MINIMUM_CANDIDATE_COUNT,
            top_k * CANDIDATE_MULTIPLIER,
        )

        candidates = self.vector_store.search(
            query_embedding=query_embedding,
            top_k=candidate_count,
            where=where_filter,
        )

        selected: list[dict[str, Any]] = []
        seen_document_ids: set[str] = set()

        for candidate in candidates:
            document_id = str(
                candidate.get("document_id")
                or candidate.get("id")
                or ""
            ).strip()

            if not document_id:
                continue

            if document_id in seen_document_ids:
                continue

            normalized = dict(candidate)

            normalized["document_id"] = (
                document_id
            )
            normalized["chunk_id"] = str(
                candidate.get("chunk_id")
                or candidate.get("id")
                or ""
            )

            selected.append(normalized)
            seen_document_ids.add(document_id)

            if len(selected) >= top_k:
                break

        return selected


@lru_cache(maxsize=1)
def get_default_statute_retriever() -> (
    StatuteRetriever
):
    """Create the default statute retriever lazily."""
    return StatuteRetriever()


def retrieve_statutes(
    query: str,
    law_id: str | None = None,
    top_k: int = 5,
) -> list[dict[str, Any]]:
    """Retrieve statute articles using the shared instance."""
    return get_default_statute_retriever().retrieve(
        query=query,
        law_id=law_id,
        top_k=top_k,
    )
