"""Retrieve statute articles from the local vector index."""

from __future__ import annotations

import re

from functools import lru_cache
from typing import Any

from rag.config import (
    CHROMA_DB_DIR,
    LEGAL_STATUTES_COLLECTION_NAME,
)
from rag.embedding_service import (
    get_default_embedding_service,
)
from rag.vector_store import ChromaVectorStore


MINIMUM_CANDIDATE_COUNT = 10
CANDIDATE_MULTIPLIER = 5


def _normalize_matching_text(
    value: object,
) -> str:
    return re.sub(
        r"[^0-9a-z\uac00-\ud7a3]+",
        "",
        str(value).casefold(),
    )


def _character_ngrams(
    text: str,
    size: int = 2,
) -> set[str]:
    if not text:
        return set()

    if len(text) < size:
        return {text}

    return {
        text[index:index + size]
        for index in range(
            len(text) - size + 1
        )
    }


ARTICLE_REFERENCE_PATTERN = re.compile(
    r"\uc81c\s*(\d+)\s*\uc870"
    r"(?:\s*\uc758\s*(\d+))?"
)


def _extract_article_labels(
    value: object,
) -> set[str]:
    labels: set[str] = set()

    for (
        article_number,
        branch_number,
    ) in ARTICLE_REFERENCE_PATTERN.findall(
        str(value)
    ):
        normalized_number = str(
            int(article_number)
        )

        label = (
            f"\uc81c{normalized_number}"
            f"\uc870"
        )

        if branch_number:
            normalized_branch = str(
                int(branch_number)
            )

            label += (
                f"\uc758{normalized_branch}"
            )

        labels.add(
            _normalize_matching_text(label)
        )

    return labels


def _calculate_lexical_boost(
    query: str,
    candidate: dict[str, Any],
) -> float:
    normalized_query = (
        _normalize_matching_text(query)
    )

    article_title = _normalize_matching_text(
        candidate.get("article_title", "")
    )
    article_label = _normalize_matching_text(
        candidate.get("article_label", "")
    )
    law_name = _normalize_matching_text(
        candidate.get("law_name", "")
    )

    boost = 0.0

    article_references = (
        _extract_article_labels(query)
    )

    if (
        article_label
        and article_label in article_references
    ):
        boost += 0.25

    if (
        article_title
        and article_title in normalized_query
    ):
        boost += 0.15

    elif article_title:
        title_ngrams = _character_ngrams(
            article_title
        )
        query_ngrams = _character_ngrams(
            normalized_query
        )

        if title_ngrams:
            overlap_ratio = (
                len(
                    title_ngrams
                    & query_ngrams
                )
                / len(title_ngrams)
            )

            boost += min(
                0.12,
                overlap_ratio * 0.12,
            )

    if law_name and law_name in normalized_query:
        boost += 0.04

    return boost


def rerank_statute_candidates(
    query: str,
    candidates: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Combine vector similarity with small lexical boosts."""
    reranked: list[dict[str, Any]] = []

    for original_rank, candidate in enumerate(
        candidates
    ):
        normalized = dict(candidate)

        similarity = float(
            normalized.get(
                "similarity",
                0.0,
            )
        )

        normalized["rerank_score"] = (
            similarity
            + _calculate_lexical_boost(
                query,
                normalized,
            )
        )
        normalized["_original_rank"] = (
            original_rank
        )

        reranked.append(normalized)

    reranked.sort(
        key=lambda item: (
            float(
                item.get(
                    "rerank_score",
                    0.0,
                )
            ),
            float(
                item.get(
                    "similarity",
                    0.0,
                )
            ),
            -int(
                item.get(
                    "_original_rank",
                    0,
                )
            ),
        ),
        reverse=True,
    )

    for candidate in reranked:
        candidate.pop(
            "_original_rank",
            None,
        )

    return reranked


class StatuteRetriever:
    """Search statute chunks and return unique articles."""

    def __init__(
        self,
        embedding_service: Any | None = None,
        vector_store: Any | None = None,
    ) -> None:
        if embedding_service is None:
            embedding_service = (
                get_default_embedding_service()
            )

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

        return rerank_statute_candidates(
            query=clean_query,
            candidates=selected,
        )[:top_k]


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
