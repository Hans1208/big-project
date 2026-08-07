"""Retrieve precedent cases from the local vector index."""

from __future__ import annotations

import re
from functools import lru_cache
from typing import Any

from rag.config import (
    CHROMA_DB_DIR,
    LEGAL_PRECEDENTS_COLLECTION_NAME,
)
from rag.embedding_service import (
    get_default_embedding_service,
)
from rag.vector_store import ChromaVectorStore


MINIMUM_CANDIDATE_COUNT = 15
CANDIDATE_MULTIPLIER = 6

SECTION_BOOSTS = {
    "holding": 0.08,
    "summary": 0.05,
    "full_text": 0.0,
}


def _normalize_text(value: object) -> str:
    return re.sub(
        r"[^0-9a-z가-힣]+",
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


def _lexical_boost(
    query: str,
    candidate: dict[str, Any],
) -> float:
    normalized_query = _normalize_text(query)
    case_name = _normalize_text(
        candidate.get("case_name", "")
    )
    referenced_statutes = _normalize_text(
        candidate.get(
            "referenced_statutes",
            "",
        )
    )

    boost = SECTION_BOOSTS.get(
        str(
            candidate.get(
                "section_type",
                "",
            )
        ),
        0.0,
    )

    if (
        case_name
        and (
            case_name in normalized_query
            or normalized_query in case_name
        )
    ):
        boost += 0.20
    elif case_name:
        case_ngrams = _character_ngrams(
            case_name
        )
        query_ngrams = _character_ngrams(
            normalized_query
        )

        if case_ngrams:
            ratio = len(
                case_ngrams & query_ngrams
            ) / len(case_ngrams)

            boost += min(
                0.12,
                ratio * 0.12,
            )

    if (
        referenced_statutes
        and referenced_statutes
        in normalized_query
    ):
        boost += 0.05

    if (
        candidate.get("court_level")
        == "SUPREME"
    ):
        boost += 0.03

    return boost


def rerank_precedent_candidates(
    query: str,
    candidates: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Rerank chunks using similarity and legal metadata."""
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
            + _lexical_boost(
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


class PrecedentRetriever:
    """Search chunks and return one result per precedent."""

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
                    LEGAL_PRECEDENTS_COLLECTION_NAME
                ),
            )

        self.embedding_service = (
            embedding_service
        )
        self.vector_store = vector_store

    def retrieve(
        self,
        query: str,
        court_level: str | None = None,
        top_k: int = 5,
    ) -> list[dict[str, Any]]:
        clean_query = query.strip()

        if not clean_query:
            raise ValueError(
                "query must not be empty."
            )

        if top_k < 1:
            raise ValueError(
                "top_k must be at least 1."
            )

        clean_court_level = (
            court_level.strip().upper()
            if court_level is not None
            else ""
        )

        if (
            clean_court_level
            and clean_court_level
            not in {
                "SUPREME",
                "LOWER",
            }
        ):
            raise ValueError(
                "court_level must be "
                "SUPREME or LOWER."
            )

        where_filter = (
            {
                "court_level": (
                    clean_court_level
                )
            }
            if clean_court_level
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

        reranked = rerank_precedent_candidates(
            query=clean_query,
            candidates=candidates,
        )

        selected: list[dict[str, Any]] = []
        seen_precedent_ids: set[str] = set()

        for candidate in reranked:
            precedent_id = str(
                candidate.get(
                    "precedent_id",
                    "",
                )
            ).strip()

            if not precedent_id:
                continue

            if precedent_id in seen_precedent_ids:
                continue

            normalized = dict(candidate)

            normalized["chunk_id"] = str(
                candidate.get("id", "")
            )

            selected.append(normalized)
            seen_precedent_ids.add(
                precedent_id
            )

            if len(selected) >= top_k:
                break

        return selected


@lru_cache(maxsize=1)
def get_default_precedent_retriever() -> (
    PrecedentRetriever
):
    return PrecedentRetriever()


def retrieve_precedents(
    query: str,
    court_level: str | None = None,
    top_k: int = 5,
) -> list[dict[str, Any]]:
    return (
        get_default_precedent_retriever()
        .retrieve(
            query=query,
            court_level=court_level,
            top_k=top_k,
        )
    )