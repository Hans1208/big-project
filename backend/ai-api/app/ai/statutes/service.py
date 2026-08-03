"""Connect structured consultation analysis to statute RAG."""

from __future__ import annotations

import json
import logging

from collections.abc import Callable
from typing import Any

from app.ai.statutes.rag_results import (
    search_statute_rag,
)


logger = logging.getLogger(__name__)


EMPTY_CONSULT_SECTION_LABELS = frozenset(
    {
        "[\uc694\uc57d]",
        "[\uc0c1\uc138]",
        "[\ucd94\ucd9c\ub41c "
        "\ucca8\ubd80\ub0b4\uc6a9]",
    }
)


def _clean_fallback_text(
    value: object,
) -> str:
    meaningful_lines = [
        line
        for raw_line in str(
            value or ""
        ).splitlines()
        if (
            line := raw_line.strip()
        )
        and line
        not in EMPTY_CONSULT_SECTION_LABELS
    ]

    return "\n".join(
        meaningful_lines
    )


def _clean_value(
    value: object,
) -> str:
    if value is None:
        return ""

    return str(value).strip()


def _serialize_extracted(
    extracted: object,
) -> str:
    if extracted is None:
        return ""

    if extracted == {} or extracted == []:
        return ""

    try:
        return json.dumps(
            extracted,
            ensure_ascii=False,
            sort_keys=True,
            default=str,
        )
    except (TypeError, ValueError):
        return _clean_value(extracted)


def build_statute_query(
    analysis: Any,
    fallback_text: str = "",
) -> str:
    """Build a focused statute query from analysis output."""
    summary = _clean_value(
        getattr(
            analysis,
            "summary",
            None,
        )
    )
    case_type = _clean_value(
        getattr(
            analysis,
            "case_type",
            None,
        )
    )
    case_subtype = _clean_value(
        getattr(
            analysis,
            "case_subtype",
            None,
        )
    )
    extracted = _serialize_extracted(
        getattr(
            analysis,
            "extracted",
            None,
        )
    )

    query_parts: list[str] = []

    if summary:
        query_parts.append(
            f"\uc0ac\uac74\uc694\uc57d: {summary}"
        )

    if case_type:
        query_parts.append(
            f"\uc0ac\uac74\uc720\ud615: {case_type}"
        )

    if case_subtype:
        query_parts.append(
            f"\uc138\ubd80\uc720\ud615: {case_subtype}"
        )

    if extracted:
        query_parts.append(
            f"\ucd94\ucd9c\uc815\ubcf4: {extracted}"
        )

    if query_parts:
        return "\n".join(query_parts)

    return _clean_fallback_text(
        fallback_text
    )


def find_related_statutes(
    analysis: Any,
    fallback_text: str = "",
    top_n: int = 5,
    search: Callable[
        ...,
        list[dict[str, Any]],
    ] = search_statute_rag,
) -> list[dict[str, Any]]:
    """Search statutes using structured analysis when available."""
    if top_n < 1:
        raise ValueError(
            "top_n must be at least 1."
        )

    query_text = build_statute_query(
        analysis=analysis,
        fallback_text=fallback_text,
    )

    if not query_text:
        return []

    try:
        return search(
            query_text=query_text,
            top_n=top_n,
        )
    except Exception:
        logger.exception(
            "Related statute search failed; "
            "continuing without statute results."
        )
        return []
