"""Adapt RAG search results for the form recommender."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from rag.form_retriever import retrieve_forms


LEGAL_INTENT_TERMS: tuple[str, ...] = (
    "\uc7ac\uc0b0\ubd84\ud560",
    "\uc591\uc721\ube44",
    "\uac1c\uba85",
    "\uc0c1\uc18d",
    "\uc0c1\uc18d\ud3ec\uae30",
    "\ud55c\uc815\uc2b9\uc778",
    "\uc131\ub144\ud6c4\uacac",
    "\ud6c4\uacac\uac1c\uc2dc",
    "\ub4f1\ub85d\ubd80\uc815\uc815",
    "\uce5c\uad8c\ud589\uc0ac\uc790",
    "\uce5c\uad8c\uc790\uc9c0\uc815",
    "\uba74\uc811\uad50\uc12d",
    "\uc704\uc790\ub8cc",
)

SECONDARY_PROCEDURE_TERMS: tuple[str, ...] = (
    "\uacbd\uc815",
    "\ucde8\uc18c",
    "\ubcc0\uacbd",
    "\uc5f0\uc7a5",
    "\ud68c\ubcf5",
    "\uc885\ub8cc",
    "\uc0ac\uc784",
)


def _normalize_for_rerank(
    value: str,
) -> str:
    """Normalize Korean text for lightweight reranking."""
    return "".join(
        character
        for character in value.casefold()
        if character.isalnum()
    )


def _extract_query_terms(
    query_text: str,
) -> tuple[str, ...]:
    """Extract supported legal intent terms from a query."""
    normalized_query = _normalize_for_rerank(
        query_text
    )

    return tuple(
        normalized_term
        for term in LEGAL_INTENT_TERMS
        if (
            normalized_term
            := _normalize_for_rerank(term)
        )
        in normalized_query
    )


def _candidate_rerank_score(
    candidate: dict[str, Any],
    query_terms: tuple[str, ...],
    normalized_query: str,
) -> float:
    """Combine semantic similarity with small title bonuses."""
    normalized_title = _normalize_for_rerank(
        str(candidate.get("name", ""))
    )

    keyword_hits = sum(
        1
        for term in query_terms
        if term in normalized_title
    )

    secondary_penalties = sum(
        1
        for term in SECONDARY_PROCEDURE_TERMS
        if (
            normalized_term
            := _normalize_for_rerank(term)
        )
        in normalized_title
        and normalized_term not in normalized_query
    )

    return (
        float(candidate.get("similarity", 0.0))
        + keyword_hits * 0.02
        - secondary_penalties * 0.01
    )


def _rerank_candidates(
    query_text: str,
    candidates: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Rerank candidates without changing their public fields."""
    query_terms = _extract_query_terms(
        query_text
    )

    if not query_terms:
        return candidates

    normalized_query = _normalize_for_rerank(
        query_text
    )

    return sorted(
        candidates,
        key=lambda candidate: _candidate_rerank_score(
            candidate,
            query_terms,
            normalized_query,
        ),
        reverse=True,
    )


def convert_rag_result_to_candidate(
    result: dict[str, Any],
) -> dict[str, Any]:
    """Convert one RAG result to recommender format."""
    return {
        "tmpltNo": str(
            result.get("document_id", "")
        ),
        "name": str(
            result.get("title", "")
        ),
        "main": str(
            result.get("case_type", "")
        ),
        "sub": str(
            result.get("case_subtype", "")
        ),
        "similarity": float(
            result.get("similarity", 0.0)
        ),
        "chunk_id": str(
            result.get("chunk_id", "")
        ),
        "source": str(
            result.get("source", "")
        ),
    }


def convert_rag_results_to_candidates(
    results: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Convert valid RAG results to candidates."""
    candidates: list[dict[str, Any]] = []
    seen_sources: set[str] = set()

    for result in results:
        candidate = convert_rag_result_to_candidate(
            result
        )

        if not candidate["tmpltNo"]:
            continue

        if not candidate["name"]:
            continue

        source_key = str(
            candidate.get("source", "")
        ).strip()

        source_key = source_key.replace(
            "\\",
            "/",
        ).casefold()

        if source_key in seen_sources:
            continue

        if source_key:
            seen_sources.add(source_key)

        candidates.append(candidate)

    return candidates



def search_rag_candidates(
    query_text: str,
    top_n: int = 10,
    retrieve: Callable[..., list[dict[str, Any]]] = (
        retrieve_forms
    ),
    case_type: str | None = None,
    case_subtype: str | None = None,
    classification_confidence: float | None = None,
) -> list[dict[str, Any]]:
    """Search the local RAG index for form candidates."""
    clean_query = query_text.strip()

    if not clean_query:
        return []

    if top_n < 1:
        raise ValueError(
            "top_n must be at least 1."
        )

    retrieve_kwargs: dict[str, Any] = {
        "query": clean_query,
        "top_k": top_n,
    }

    if case_type is not None:
        retrieve_kwargs["case_type"] = case_type

    if case_subtype is not None:
        retrieve_kwargs["case_subtype"] = (
            case_subtype
        )

    if classification_confidence is not None:
        retrieve_kwargs[
            "classification_confidence"
        ] = classification_confidence

    results = retrieve(**retrieve_kwargs)

    candidates = convert_rag_results_to_candidates(
        results
    )

    return _rerank_candidates(
        clean_query,
        candidates,
    )
