"""Adapt statute RAG results for application services."""

from __future__ import annotations

import logging

from collections.abc import Callable
from typing import Any

from rag.statute_retriever import (
    retrieve_statutes,
)


logger = logging.getLogger(__name__)


def _build_citation(
    result: dict[str, Any],
) -> str:
    law_name = str(
        result.get("law_name", "")
    ).strip()

    article_label = str(
        result.get("article_label", "")
    ).strip()

    article_title = str(
        result.get("article_title", "")
    ).strip()

    citation = " ".join(
        part
        for part in (
            law_name,
            article_label,
        )
        if part
    )

    if article_title:
        citation += f"({article_title})"

    return citation


def convert_rag_result_to_statute(
    result: dict[str, Any],
) -> dict[str, Any]:
    """Convert one internal RAG result to application format."""
    similarity = float(
        result.get(
            "similarity",
            0.0,
        )
    )

    return {
        "document_id": str(
            result.get("document_id", "")
        ),
        "chunk_id": str(
            result.get("chunk_id", "")
            or result.get("id", "")
        ),
        "law_id": str(
            result.get("law_id", "")
        ),
        "law_name": str(
            result.get("law_name", "")
        ),
        "article_number": str(
            result.get("article_number", "")
        ),
        "article_branch_number": str(
            result.get(
                "article_branch_number",
                "",
            )
        ),
        "article_label": str(
            result.get("article_label", "")
        ),
        "article_title": str(
            result.get("article_title", "")
        ),
        "citation": _build_citation(
            result
        ),
        "effective_date": str(
            result.get("effective_date", "")
        ),
        "content": str(
            result.get("content", "")
        ),
        "similarity": similarity,
        "rerank_score": float(
            result.get(
                "rerank_score",
                similarity,
            )
        ),
        "source": str(
            result.get("source", "")
        ),
    }


def convert_rag_results_to_statutes(
    results: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Convert valid unique article results."""
    converted_results: list[dict[str, Any]] = []
    seen_document_ids: set[str] = set()

    for result in results:
        converted = (
            convert_rag_result_to_statute(
                result
            )
        )

        document_id = converted[
            "document_id"
        ].strip()

        if not document_id:
            continue

        if not converted["law_name"].strip():
            continue

        if not converted[
            "article_label"
        ].strip():
            continue

        if document_id in seen_document_ids:
            continue

        seen_document_ids.add(document_id)
        converted_results.append(converted)

    return converted_results


def search_statute_rag(
    query_text: str,
    top_n: int = 5,
    law_id: str | None = None,
    retrieve: Callable[
        ...,
        list[dict[str, Any]],
    ] = retrieve_statutes,
) -> list[dict[str, Any]]:
    """Search statutes without propagating local RAG failures."""
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

    if law_id is not None:
        clean_law_id = law_id.strip()

        if clean_law_id:
            retrieve_kwargs[
                "law_id"
            ] = clean_law_id

    try:
        results = retrieve(
            **retrieve_kwargs
        )
    except Exception:
        logger.exception(
            "Local statute RAG retrieval failed."
        )
        return []

    return convert_rag_results_to_statutes(
        results
    )


def build_statute_context(
    statutes: list[dict[str, Any]],
    max_characters: int = 6000,
) -> str:
    """Format statute results for an LLM prompt or response."""
    if max_characters < 1:
        raise ValueError(
            "max_characters must be at least 1."
        )

    blocks: list[str] = []
    current_length = 0

    for index, statute in enumerate(
        statutes,
        start=1,
    ):
        citation = str(
            statute.get("citation", "")
        ).strip()

        content = str(
            statute.get("content", "")
        ).strip()

        effective_date = str(
            statute.get(
                "effective_date",
                "",
            )
        ).strip()

        if not citation or not content:
            continue

        lines = [
            f"[{index}] {citation}",
        ]

        if effective_date:
            lines.append(
                f"\uc2dc\ud589\uc77c: "
                f"{effective_date}"
            )

        lines.append(
            f"\ub0b4\uc6a9: {content}"
        )

        block = "\n".join(lines)

        separator_length = (
            2 if blocks else 0
        )

        next_length = (
            current_length
            + separator_length
            + len(block)
        )

        if next_length > max_characters:
            if not blocks:
                blocks.append(
                    block[:max_characters]
                )

            break

        blocks.append(block)
        current_length = next_length

    return "\n\n".join(blocks)
