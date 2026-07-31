"""Retrieve unique legal forms from the vector index."""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from rag.classification import build_where_filter
from rag.config import (
    CHROMA_DB_DIR,
    LEGAL_FORMS_COLLECTION_NAME,
)
from rag.embedding_service import EmbeddingService
from rag.vector_store import ChromaVectorStore


HIGH_CONFIDENCE = 0.75
MEDIUM_CONFIDENCE = 0.50

MINIMUM_CANDIDATE_COUNT = 10
CANDIDATE_MULTIPLIER = 5


def build_filter_chain(
    case_type: str | None = None,
    case_subtype: str | None = None,
    classification_confidence: float | None = None,
) -> list[dict[str, Any] | None]:
    """Build filters from strict to broad."""
    if classification_confidence is None:
        if case_type and case_subtype:
            return [
                build_where_filter(
                    case_type=case_type,
                    case_subtype=case_subtype,
                ),
                build_where_filter(
                    case_type=case_type,
                ),
                None,
            ]

        if case_type:
            return [
                build_where_filter(
                    case_type=case_type,
                ),
                None,
            ]

        return [None]

    if (
        classification_confidence >= HIGH_CONFIDENCE
        and case_type
        and case_subtype
    ):
        return [
            build_where_filter(
                case_type=case_type,
                case_subtype=case_subtype,
            ),
            build_where_filter(
                case_type=case_type,
            ),
            None,
        ]

    if (
        classification_confidence >= MEDIUM_CONFIDENCE
        and case_type
    ):
        return [
            build_where_filter(
                case_type=case_type,
            ),
            None,
        ]

    return [None]


class FormRetriever:
    """Search and deduplicate legal-form chunks."""

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
                    LEGAL_FORMS_COLLECTION_NAME
                ),
            )

        self.embedding_service = embedding_service
        self.vector_store = vector_store

    def retrieve(
        self,
        query: str,
        case_type: str | None = None,
        case_subtype: str | None = None,
        classification_confidence: float | None = None,
        top_k: int = 3,
    ) -> list[dict[str, Any]]:
        """Return unique forms ordered by filter priority."""
        clean_query = query.strip()

        if not clean_query:
            raise ValueError(
                "query must not be empty."
            )

        if top_k < 1:
            raise ValueError(
                "top_k must be at least 1."
            )

        query_embedding = (
            self.embedding_service.embed_query(
                clean_query
            )
        )

        filters = build_filter_chain(
            case_type=case_type,
            case_subtype=case_subtype,
            classification_confidence=(
                classification_confidence
            ),
        )

        candidate_count = max(
            MINIMUM_CANDIDATE_COUNT,
            top_k * CANDIDATE_MULTIPLIER,
        )

        selected: list[dict[str, Any]] = []
        seen_document_ids: set[str] = set()
        seen_sources: set[str] = set()

        for where_filter in filters:
            candidates = self.vector_store.search(
                query_embedding=query_embedding,
                top_k=candidate_count,
                where=where_filter,
            )

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

                source_key = str(
                    candidate.get("source")
                    or ""
                ).strip()

                source_key = source_key.replace(
                    "\\",
                    "/",
                ).casefold()

                if (
                    source_key
                    and source_key in seen_sources
                ):
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

                if source_key:
                    seen_sources.add(source_key)

                if len(selected) >= top_k:
                    return selected

        return selected


@lru_cache(maxsize=1)
def get_default_form_retriever() -> FormRetriever:
    """Create the default retriever lazily once."""
    return FormRetriever()


def retrieve_forms(
    query: str,
    case_type: str | None = None,
    case_subtype: str | None = None,
    classification_confidence: float | None = None,
    top_k: int = 3,
) -> list[dict[str, Any]]:
    """Retrieve forms with the shared default retriever."""
    return get_default_form_retriever().retrieve(
        query=query,
        case_type=case_type,
        case_subtype=case_subtype,
        classification_confidence=(
            classification_confidence
        ),
        top_k=top_k,
    )
