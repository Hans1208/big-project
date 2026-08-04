"""Normalize precedent detail API payloads."""

from __future__ import annotations

import html
import re
from collections.abc import Iterable
from typing import Any


class PrecedentParseError(ValueError):
    """Raised when a precedent payload has an invalid shape."""


COURT_LEVELS = {
    "400201": "SUPREME",
    "400202": "LOWER",
}


def _raw_text(value: Any) -> str:
    if value is None:
        return ""

    if isinstance(value, dict):
        value = value.get("content", "")

    return str(value)


def _clean_text(value: Any) -> str:
    text = html.unescape(
        _raw_text(value)
    )

    text = re.sub(
        r"(?i)<br\s*/?>",
        "\n",
        text,
    )
    text = re.sub(
        r"(?i)</(?:p|div|li)>",
        "\n",
        text,
    )
    text = re.sub(
        r"<[^>]+>",
        "",
        text,
    )

    normalized_lines = [
        " ".join(line.split())
        for line in text.replace(
            "\r\n",
            "\n",
        ).replace(
            "\r",
            "\n",
        ).split("\n")
    ]

    return "\n".join(
        line
        for line in normalized_lines
        if line
    )


def _normalize_date(value: Any) -> str:
    return "".join(
        character
        for character in _clean_text(value)
        if character.isdigit()
    )


def _first_text(
    primary: dict[str, Any],
    fallback: dict[str, Any],
    *keys: str,
) -> str:
    for source in (
        primary,
        fallback,
    ):
        for key in keys:
            value = _clean_text(
                source.get(key)
            )

            if value:
                return value

    return ""


def _normalize_matches(
    values: Iterable[str],
) -> list[str]:
    return sorted(
        {
            value.strip()
            for value in values
            if value.strip()
        }
    )


def parse_precedent_payload(
    payload: dict[str, Any],
    *,
    list_item: dict[str, Any] | None = None,
    matched_searches: Iterable[str] = (),
) -> dict[str, Any]:
    """Convert one precedent response to a normalized record."""
    root = payload.get("PrecService")

    if not isinstance(root, dict):
        raise PrecedentParseError(
            "PrecService response is missing."
        )

    fallback = list_item or {}

    precedent_id = _first_text(
        root,
        fallback,
        "판례정보일련번호",
        "판례일련번호",
        "precedent_id",
    )
    case_name = _first_text(
        root,
        fallback,
        "사건명",
        "case_name",
    )
    case_number = _first_text(
        root,
        fallback,
        "사건번호",
        "case_number",
    )

    if not precedent_id:
        raise PrecedentParseError(
            "precedent ID is missing."
        )

    if not case_name:
        raise PrecedentParseError(
            "case name is missing."
        )

    court_type_code = _first_text(
        root,
        fallback,
        "법원종류코드",
        "court_type_code",
    )

    holding = _first_text(
        root,
        fallback,
        "판시사항",
        "holding",
    )
    judgment_summary = _first_text(
        root,
        fallback,
        "판결요지",
        "summary",
    )
    full_text = _first_text(
        root,
        fallback,
        "판례내용",
        "full_text",
    )

    if not any(
        (
            holding,
            judgment_summary,
            full_text,
        )
    ):
        raise PrecedentParseError(
            "precedent searchable text is missing."
        )

    return {
        "precedent_id": precedent_id,
        "case_name": case_name,
        "case_number": case_number,
        "decision_date": _normalize_date(
            _first_text(
                root,
                fallback,
                "선고일자",
                "decision_date",
            )
        ),
        "decision": _first_text(
            root,
            fallback,
            "선고",
            "decision",
        ),
        "court_name": _first_text(
            root,
            fallback,
            "법원명",
            "court_name",
        ),
        "court_type_code": court_type_code,
        "court_level": COURT_LEVELS.get(
            court_type_code,
            "UNKNOWN",
        ),
        "case_type_name": _first_text(
            root,
            fallback,
            "사건종류명",
            "case_type_name",
        ),
        "case_type_code": _first_text(
            root,
            fallback,
            "사건종류코드",
            "case_type_code",
        ),
        "decision_type": _first_text(
            root,
            fallback,
            "판결유형",
            "decision_type",
        ),
        "holding": holding,
        "summary": judgment_summary,
        "referenced_statutes": _first_text(
            root,
            fallback,
            "참조조문",
            "referenced_statutes",
        ),
        "referenced_precedents": _first_text(
            root,
            fallback,
            "참조판례",
            "referenced_precedents",
        ),
        "full_text": full_text,
        "matched_searches": _normalize_matches(
            matched_searches
        ),
        "source": (
            f"law_api:prec:{precedent_id}"
        ),
    }