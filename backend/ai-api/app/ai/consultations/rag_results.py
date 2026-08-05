"""Adapt consultation RAG results for application use."""

from __future__ import annotations

import logging

from collections.abc import Callable
from typing import Any

from rag.consultation_retriever import (
    retrieve_consultations,
)


logger = logging.getLogger(__name__)

DEFAULT_EXCERPT_LENGTH = 600

CONTEXT_HEADER = (
    "[\uc720\uc0ac \uc0c1\ub2f4\uc0ac\ub840 "
    "\u2014 \ubc95\uc801 \uadfc\uac70\uac00 "
    "\uc544\ub2cc \ucc38\uace0\uc790\ub8cc]"
)


def _text(
    result: dict[str, Any],
    key: str,
) -> str:
    return str(
        result.get(
            key,
            "",
        )
        or ""
    ).strip()


def _excerpt(
    value: object,
    max_characters: int = (
        DEFAULT_EXCERPT_LENGTH
    ),
) -> str:
    if max_characters < 1:
        raise ValueError(
            "max_characters must be "
            "at least 1."
        )

    text = str(
        value or ""
    ).strip()

    if len(text) <= max_characters:
        return text

    if max_characters == 1:
        return "\u2026"

    return (
        text[
            :max_characters - 1
        ]
        + "\u2026"
    )


def convert_rag_result_to_consultation(
    result: dict[str, Any],
) -> dict[str, Any]:
    similarity = float(
        result.get(
            "similarity",
            0.0,
        )
        or 0.0
    )

    answer = (
        _text(
            result,
            "answer",
        )
        or _text(
            result,
            "content",
        )
    )

    return {
        "consultation_id": _text(
            result,
            "consultation_id",
        ),
        "chunk_id": (
            _text(
                result,
                "chunk_id",
            )
            or _text(
                result,
                "id",
            )
        ),
        "source_type": _text(
            result,
            "source_type",
        ),
        "service_category": _text(
            result,
            "service_category",
        ),
        "legal_path": _text(
            result,
            "legal_path",
        ),
        "question": _text(
            result,
            "question",
        ),
        "answer_excerpt": (
            _excerpt(answer)
        ),
        "similarity": similarity,
        "rerank_score": float(
            result.get(
                "rerank_score",
                similarity,
            )
            or similarity
        ),
        "source_date": _text(
            result,
            "source_date",
        ),
    }


def convert_rag_results_to_consultations(
    results: list[
        dict[str, Any]
    ],
) -> list[dict[str, Any]]:
    converted_results: list[
        dict[str, Any]
    ] = []

    seen_ids: set[str] = set()

    for result in results:
        converted = (
            convert_rag_result_to_consultation(
                result
            )
        )

        consultation_id = converted[
            "consultation_id"
        ]

        if not consultation_id:
            continue

        if not converted["question"]:
            continue

        if not converted[
            "answer_excerpt"
        ]:
            continue

        if consultation_id in seen_ids:
            continue

        seen_ids.add(
            consultation_id
        )

        converted_results.append(
            converted
        )

    return converted_results


def search_consultation_rag(
    query_text: str,
    top_n: int = 3,
    retrieve: Callable[
        ...,
        list[dict[str, Any]],
    ] = retrieve_consultations,
) -> list[dict[str, Any]]:
    clean_query = str(
        query_text or ""
    ).strip()

    if not clean_query:
        return []

    if top_n < 1:
        raise ValueError(
            "top_n must be at least 1."
        )

    try:
        results = retrieve(
            query=clean_query,
            top_k=top_n,
        )
    except Exception:
        logger.exception(
            "Local consultation RAG "
            "retrieval failed."
        )
        return []

    return (
        convert_rag_results_to_consultations(
            results
        )
    )


def build_consultation_context(
    consultations: list[
        dict[str, Any]
    ],
    max_characters: int = 5000,
) -> str:
    if max_characters < 1:
        raise ValueError(
            "max_characters must be "
            "at least 1."
        )

    if not consultations:
        return ""

    if len(CONTEXT_HEADER) >= max_characters:
        return CONTEXT_HEADER[
            :max_characters
        ]

    blocks = [
        CONTEXT_HEADER
    ]

    current_length = len(
        CONTEXT_HEADER
    )

    for index, consultation in enumerate(
        consultations,
        start=1,
    ):
        legal_path = str(
            consultation.get(
                "legal_path",
                "",
            )
            or ""
        ).strip()

        source_type = str(
            consultation.get(
                "source_type",
                "",
            )
            or ""
        ).strip()

        question = str(
            consultation.get(
                "question",
                "",
            )
            or ""
        ).strip()

        answer_excerpt = str(
            consultation.get(
                "answer_excerpt",
                "",
            )
            or ""
        ).strip()

        source_date = str(
            consultation.get(
                "source_date",
                "",
            )
            or ""
        ).strip()

        if not question or not answer_excerpt:
            continue

        lines = [
            (
                f"[{index}] "
                f"{legal_path}"
            ).strip(),
            (
                f"\uc720\ud615: "
                f"{source_type}"
            ),
            (
                f"\uc9c8\ubb38: "
                f"{question}"
            ),
            (
                f"\ub2f5\ubcc0: "
                f"{answer_excerpt}"
            ),
        ]

        if source_date:
            lines.append(
                f"\uc790\ub8cc\uc77c: "
                f"{source_date}"
            )

        block = "\n".join(
            lines
        )

        separator_length = 2

        remaining = (
            max_characters
            - current_length
            - separator_length
        )

        if remaining <= 0:
            break

        if len(block) > remaining:
            blocks.append(
                block[:remaining]
            )
            current_length = (
                max_characters
            )
            break

        blocks.append(block)

        current_length += (
            separator_length
            + len(block)
        )

    return "\n\n".join(
        blocks
    )[:max_characters]
