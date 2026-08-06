"""Normalize family-law consultation records."""

from __future__ import annotations

import hashlib
import html
import json
import re

from collections import Counter
from collections.abc import Sequence
from dataclasses import asdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from rag.consultation_loader import (
    RawConsultationRow,
)


HTML_TAG_PATTERN = re.compile(
    r"<[^>]+>"
)
WHITESPACE_PATTERN = re.compile(
    r"\s+"
)
CONTACT_FOOTER_PATTERN = re.compile(
    r"\s*\u203b\s*\uc790\uc138\ud55c\s*"
    r"\uc0ac\ud56d\uc740.*?"
    r"\ubb38\uc758\ud558\uc2dc\uae30\s*"
    r"\ubc14\ub78d\ub2c8\ub2e4\.?\s*$",
    re.DOTALL,
)

PERSONAL_INFORMATION_PATTERNS = (
    (
        "resident_registration_number",
        re.compile(
            r"(?<!\d)"
            r"\d{6}\s*-\s*[1-4]\d{6}"
            r"(?!\d)"
        ),
    ),
    (
        "phone",
        re.compile(
            r"(?<!\d)"
            r"(?:01[016789]|02|0[3-6][1-5])"
            r"[-\s]?\d{3,4}"
            r"[-\s]?\d{4}"
            r"(?!\d)"
        ),
    ),
    (
        "email",
        re.compile(
            r"\b[A-Za-z0-9._%+-]+"
            r"@[A-Za-z0-9.-]+"
            r"\.[A-Za-z]{2,}\b"
        ),
    ),
)


@dataclass(
    frozen=True,
    slots=True,
)
class NormalizedConsultation:
    consultation_id: str
    source_type: str
    service_category: str
    legal_path: str
    question: str
    answer: str
    source_file: str
    source_row: int
    source_date: str = "2024-07-31"


class ConsultationNormalizationError(
    RuntimeError
):
    """Raised when consultation normalization cannot continue."""


class PersonalInformationDetectedError(
    ConsultationNormalizationError
):
    """Raised when a personal-information candidate remains."""

    def __init__(
        self,
        report: dict[str, Any],
    ) -> None:
        super().__init__(
            "Personal-information candidates "
            "were found in consultation data."
        )
        self.report = report


def normalize_text(
    value: object,
) -> str:
    text = html.unescape(
        str(value or "")
    )

    text = HTML_TAG_PATTERN.sub(
        " ",
        text,
    )

    text = text.replace(
        "\xa0",
        " ",
    )

    return WHITESPACE_PATTERN.sub(
        " ",
        text,
    ).strip()


def _remove_contact_footer(
    answer: str,
) -> tuple[str, bool]:
    cleaned = CONTACT_FOOTER_PATTERN.sub(
        "",
        answer,
    ).strip()

    return (
        cleaned,
        cleaned != answer,
    )


def _is_root_or_child(
    legal_path: str,
    root: str,
) -> bool:
    return (
        legal_path == root
        or legal_path.startswith(
            root + ">"
        )
    )


def map_service_category(
    legal_path: object,
) -> str | None:
    path = normalize_text(
        legal_path
    )

    family_registration = (
        "\uac00\uc871\uad00\uacc4\ub4f1\ub85d"
    )
    inheritance = (
        "\uc0c1\uc18d\uacfc\uc720\uc5b8"
    )
    kinship = "\uce5c\uc871"

    if _is_root_or_child(
        path,
        family_registration,
    ):
        return "family_registration"

    if _is_root_or_child(
        path,
        inheritance,
    ):
        return "inheritance"

    if not _is_root_or_child(
        path,
        kinship,
    ):
        return None

    litigation_prefixes = (
        "\uce5c\uc871>\uc774\ud63c",
        (
            "\uce5c\uc871>"
            "\uc57d\ud63c\uacfc\ud63c\uc778"
        ),
        (
            "\uce5c\uc871>"
            "\uc591\uc721\uad8c\uc790\uc591\uc721\ube44"
            "\uba74\uc811\uad50\uc12d\uad8c\ub4f1"
        ),
    )

    if any(
        _is_root_or_child(
            path,
            prefix,
        )
        for prefix in litigation_prefixes
    ):
        return "family_litigation"

    if (
        "\uce5c\uad8c\uc790"
        "(\uc9c0\uc815\uacfc\ubcc0\uacbd)"
        in path
    ):
        return "family_litigation"

    return "kinship"


def _masked_value(
    value: str,
) -> str:
    if len(value) <= 4:
        return "*" * len(value)

    return (
        value[:2]
        + "*" * (len(value) - 4)
        + value[-2:]
    )


def find_personal_information_candidates(
    *,
    question: str,
    answer: str,
) -> list[dict[str, str]]:
    candidates: list[
        dict[str, str]
    ] = []

    for field, value in (
        ("question", question),
        ("answer", answer),
    ):
        for (
            kind,
            pattern,
        ) in PERSONAL_INFORMATION_PATTERNS:
            for match in pattern.finditer(
                value
            ):
                candidates.append(
                    {
                        "kind": kind,
                        "field": field,
                        "masked_value": (
                            _masked_value(
                                match.group(0)
                            )
                        ),
                    }
                )

    return candidates


def _stable_consultation_id(
    *,
    source_type: str,
    question: str,
    answer: str,
) -> str:
    stable_key = "\n".join(
        (
            source_type,
            question.casefold(),
            answer.casefold(),
        )
    )

    digest = hashlib.sha256(
        stable_key.encode("utf-8")
    ).hexdigest()[:24]

    return (
        "consultation-"
        + digest
    )


def normalize_consultations(
    rows: Sequence[
        RawConsultationRow
    ],
    *,
    fail_on_pii: bool = True,
) -> tuple[
    list[NormalizedConsultation],
    dict[str, Any],
]:
    consultations: list[
        NormalizedConsultation
    ] = []

    seen_pairs: set[
        tuple[str, str]
    ] = set()

    category_counts: Counter[
        str
    ] = Counter()

    excluded_non_family_rows = 0
    excluded_blank_rows = 0
    duplicate_rows = 0
    removed_contact_footers = 0

    personal_candidates: list[
        dict[str, Any]
    ] = []

    for row in rows:
        legal_path = normalize_text(
            row.legal_path
        )

        service_category = (
            map_service_category(
                legal_path
            )
        )

        if service_category is None:
            excluded_non_family_rows += 1
            continue

        question = normalize_text(
            row.question
        )
        answer = normalize_text(
            row.answer
        )

        (
            answer,
            footer_removed,
        ) = _remove_contact_footer(
            answer
        )

        if footer_removed:
            removed_contact_footers += 1

        if not question or not answer:
            excluded_blank_rows += 1
            continue

        candidates = (
            find_personal_information_candidates(
                question=question,
                answer=answer,
            )
        )

        for candidate in candidates:
            personal_candidates.append(
                {
                    **candidate,
                    "source_file": (
                        row.source_file
                    ),
                    "source_row": (
                        row.source_row
                    ),
                }
            )

        duplicate_key = (
            question.casefold(),
            answer.casefold(),
        )

        if duplicate_key in seen_pairs:
            duplicate_rows += 1
            continue

        seen_pairs.add(
            duplicate_key
        )

        consultations.append(
            NormalizedConsultation(
                consultation_id=(
                    _stable_consultation_id(
                        source_type=(
                            row.source_type
                        ),
                        question=question,
                        answer=answer,
                    )
                ),
                source_type=(
                    row.source_type
                ),
                service_category=(
                    service_category
                ),
                legal_path=legal_path,
                question=question,
                answer=answer,
                source_file=(
                    row.source_file
                ),
                source_row=(
                    row.source_row
                ),
            )
        )

        category_counts[
            service_category
        ] += 1

    family_candidate_rows = (
        len(rows)
        - excluded_non_family_rows
    )

    report: dict[str, Any] = {
        "input_rows": len(rows),
        "family_candidate_rows": (
            family_candidate_rows
        ),
        "excluded_non_family_rows": (
            excluded_non_family_rows
        ),
        "excluded_blank_rows": (
            excluded_blank_rows
        ),
        "duplicate_rows": duplicate_rows,
        "removed_contact_footers": (
            removed_contact_footers
        ),
        "normalized_rows": (
            len(consultations)
        ),
        "category_counts": dict(
            sorted(
                category_counts.items()
            )
        ),
        "personal_information_candidates": (
            personal_candidates
        ),
    }

    if (
        personal_candidates
        and fail_on_pii
    ):
        raise (
            PersonalInformationDetectedError(
                report
            )
        )

    return consultations, report


def write_normalized_outputs(
    consultations: Sequence[
        NormalizedConsultation
    ],
    report: dict[str, Any],
    *,
    processed_path: Path,
    report_path: Path,
) -> None:
    processed_path = Path(
        processed_path
    )
    report_path = Path(
        report_path
    )

    processed_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )
    report_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    lines = [
        json.dumps(
            asdict(consultation),
            ensure_ascii=False,
            sort_keys=True,
        )
        for consultation in consultations
    ]

    processed_path.write_text(
        (
            "\n".join(lines)
            + ("\n" if lines else "")
        ),
        encoding="utf-8",
        newline="\n",
    )

    report_path.write_text(
        json.dumps(
            report,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
        newline="\n",
    )
