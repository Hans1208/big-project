"""Adapt RAG search results for the form recommender."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from rag.form_retriever import retrieve_forms


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

    return convert_rag_results_to_candidates(
        results
    )
