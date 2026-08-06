"""Privacy boundary for consultation RAG searches."""

from __future__ import annotations

import logging

from collections.abc import (
    Callable,
    Mapping,
)
from typing import Any

from app.ai.consultations.service import (
    find_related_consultations,
)
from app.ai.precedents.service import (
    find_related_precedents,
)
from app.ai.statutes.service import (
    find_related_statutes,
)


logger = logging.getLogger(__name__)

DEFAULT_CONSULTATION_TOP_N = 3


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
    search: Callable[
        ...,
        list[dict],
    ],
    anonymized_text: str,
    top_n: int,
) -> list[dict]:
    try:
        return search(
            anonymized_text=(
                anonymized_text
            ),
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
    consultation_top_n: int = (
        DEFAULT_CONSULTATION_TOP_N
    ),
    statute_search: Callable[
        ...,
        list[dict],
    ] = find_related_statutes,
    precedent_search: Callable[
        ...,
        list[dict],
    ] = find_related_precedents,
    consultation_search: Callable[
        ...,
        list[dict],
    ] = find_related_consultations,
) -> dict[str, list[dict]]:
    if top_n < 1:
        raise ValueError(
            "top_n must be at least 1."
        )

    if consultation_top_n < 1:
        raise ValueError(
            "consultation_top_n must "
            "be at least 1."
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
            "related_consultations": [],
        }

    return {
        "related_statutes": _safe_search(
            name="statute",
            search=statute_search,
            anonymized_text=(
                anonymized_text
            ),
            top_n=top_n,
        ),
        "related_precedents": _safe_search(
            name="precedent",
            search=precedent_search,
            anonymized_text=(
                anonymized_text
            ),
            top_n=top_n,
        ),
        "related_consultations": (
            _safe_search(
                name="consultation",
                search=(
                    consultation_search
                ),
                anonymized_text=(
                    anonymized_text
                ),
                top_n=(
                    consultation_top_n
                ),
            )
        ),
    }
