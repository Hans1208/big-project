"""Privacy boundary for consultation RAG searches."""

from __future__ import annotations

import logging

from collections.abc import Callable, Mapping
from typing import Any

from app.ai.precedents.service import (
    find_related_precedents,
)
from app.ai.statutes.service import (
    find_related_statutes,
)


logger = logging.getLogger(__name__)


def _clean_anonymized_text(
    content: Mapping[str, Any],
) -> str:
    return str(
        content.get(
            "anonymized_text",
            "",
        )
        or ""
    ).strip()


def _safe_search(
    *,
    name: str,
    search: Callable[..., list[dict]],
    anonymized_text: str,
    top_n: int,
) -> list[dict]:
    try:
        return search(
            anonymized_text=anonymized_text,
            top_n=top_n,
        )
    except Exception:
        logger.exception(
            "%s RAG search failed; "
            "continuing without results.",
            name,
        )
        return []


def collect_related_legal_sources(
    *,
    content: Mapping[str, Any],
    top_n: int = 5,
    statute_search: Callable[
        ...,
        list[dict],
    ] = find_related_statutes,
    precedent_search: Callable[
        ...,
        list[dict],
    ] = find_related_precedents,
) -> dict[str, list[dict]]:
    if top_n < 1:
        raise ValueError(
            "top_n must be at least 1."
        )

    anonymized_text = (
        _clean_anonymized_text(
            content
        )
    )

    if not anonymized_text:
        return {
            "related_statutes": [],
            "related_precedents": [],
        }

    return {
        "related_statutes": _safe_search(
            name="statute",
            search=statute_search,
            anonymized_text=anonymized_text,
            top_n=top_n,
        ),
        "related_precedents": _safe_search(
            name="precedent",
            search=precedent_search,
            anonymized_text=anonymized_text,
            top_n=top_n,
        ),
    }
