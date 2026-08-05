"""Search precedents using anonymized consultation text only."""

from __future__ import annotations

import logging

from collections.abc import Callable
from typing import Any

from app.ai.precedents.rag_results import (
    search_precedent_rag,
)


logger = logging.getLogger(__name__)


def _clean_anonymized_text(
    value: object,
) -> str:
    return "\n".join(
        line
        for raw_line in str(
            value or ""
        ).splitlines()
        if (
            line := raw_line.strip()
        )
    )


def find_related_precedents(
    anonymized_text: str,
    top_n: int = 5,
    search: Callable[
        ...,
        list[dict[str, Any]],
    ] = search_precedent_rag,
) -> list[dict[str, Any]]:
    if top_n < 1:
        raise ValueError(
            "top_n must be at least 1."
        )

    query_text = _clean_anonymized_text(
        anonymized_text
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
            "Related precedent search failed; "
            "continuing without precedent results."
        )
        return []
