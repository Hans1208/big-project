"""Adapt local precedent RAG results for application use."""

from __future__ import annotations

import logging

from collections.abc import Callable
from typing import Any

from rag.precedent_retriever import (
    retrieve_precedents,
)


logger = logging.getLogger(__name__)


def _text(
    result: dict[str, Any],
    key: str,
) -> str:
    return str(
        result.get(key, "")
    ).strip()


def convert_rag_result_to_precedent(
    result: dict[str, Any],
) -> dict[str, Any]:
    similarity = float(
        result.get(
            "similarity",
            0.0,
        )
    )

    court_name = _text(
        result,
        "court_name",
    )
    decision_date = _text(
        result,
        "decision_date",
    )
    case_name = _text(
        result,
        "case_name",
    )

    citation = " ".join(
        value
        for value in (
            court_name,
            decision_date,
            case_name,
        )
        if value
    )

    return {
        "document_id": _text(
            result,
            "document_id",
        ),
        "chunk_id": (
            _text(result, "chunk_id")
            or _text(result, "id")
        ),
        "precedent_id": _text(
            result,
            "precedent_id",
        ),
        "case_name": case_name,
        "case_number": _text(
            result,
            "case_number",
        ),
        "decision_date": decision_date,
        "court_name": court_name,
        "court_level": _text(
            result,
            "court_level",
        ),
        "case_type_name": _text(
            result,
            "case_type_name",
        ),
        "decision_type": _text(
            result,
            "decision_type",
        ),
        "section_type": _text(
            result,
            "section_type",
        ),
        "section_label": _text(
            result,
            "section_label",
        ),
        "holding": _text(
            result,
            "holding",
        ),
        "summary": _text(
            result,
            "summary",
        ),
        "content": _text(
            result,
            "content",
        ),
        "referenced_statutes": _text(
            result,
            "referenced_statutes",
        ),
        "referenced_precedents": _text(
            result,
            "referenced_precedents",
        ),
        "citation": citation,
        "similarity": similarity,
        "rerank_score": float(
            result.get(
                "rerank_score",
                similarity,
            )
        ),
        "source": _text(
            result,
            "source",
        ),
    }


def convert_rag_results_to_precedents(
    results: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    converted_results: list[
        dict[str, Any]
    ] = []
    seen_precedent_ids: set[str] = set()

    for result in results:
        converted = (
            convert_rag_result_to_precedent(
                result
            )
        )

        precedent_id = converted[
            "precedent_id"
        ]

        if not precedent_id:
            continue

        if not converted["case_name"]:
            continue

        if precedent_id in seen_precedent_ids:
            continue

        seen_precedent_ids.add(
            precedent_id
        )
        converted_results.append(
            converted
        )

    return converted_results


def search_precedent_rag(
    query_text: str,
    top_n: int = 5,
    court_level: str | None = None,
    retrieve: Callable[
        ...,
        list[dict[str, Any]],
    ] = retrieve_precedents,
) -> list[dict[str, Any]]:
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

    if court_level is not None:
        clean_court_level = (
            court_level.strip().upper()
        )

        if clean_court_level:
            retrieve_kwargs[
                "court_level"
            ] = clean_court_level

    try:
        results = retrieve(
            **retrieve_kwargs
        )
    except Exception:
        logger.exception(
            "Local precedent RAG retrieval failed."
        )
        return []

    return (
        convert_rag_results_to_precedents(
            results
        )
    )
