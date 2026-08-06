"""Load Korea Legal Aid consultation CSV sources."""

from __future__ import annotations

import csv

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path


CLASSIFICATION_COLUMN = (
    "\ubc95\ub960\ubd84\ub958"
)
BASIC_QUESTION_COLUMN = (
    "\uae30\ubcf8\uc9c8\ubb38"
)
BASIC_ANSWER_COLUMN = (
    "\uae30\ubcf8\ub2f5\ubcc0"
)
CASE_QUESTION_COLUMN = (
    "\uc720\uc0ac\uc9c8\ubb38"
)
CASE_ANSWER_COLUMN = (
    "\uc720\uc0ac\ub2f5\ubcc0"
)
PRIMARY_STATUTES_COLUMN = (
    "\uc8fc\uc694\ubc95\ub839"
)
PRECEDENTS_COLUMN = "\ud310\ub840"


class ConsultationSourceError(
    RuntimeError
):
    """Raised when a consultation CSV violates its source contract."""


@dataclass(
    frozen=True,
    slots=True,
)
class ConsultationSourceSpec:
    """Expected structure for one consultation CSV source."""

    key: str
    path: Path
    source_type: str
    classification_column: str
    question_column: str
    answer_column: str
    expected_header: tuple[str, ...]
    expected_rows: int
    expected_family_rows: int


@dataclass(
    frozen=True,
    slots=True,
)
class RawConsultationRow:
    """One unnormalized consultation row with source metadata."""

    source_key: str
    source_type: str
    source_file: str
    source_row: int
    legal_path: str
    question: str
    answer: str
    primary_statutes: str = ""
    precedents: str = ""


def default_source_specs(
    raw_dir: Path,
) -> tuple[
    ConsultationSourceSpec,
    ...,
]:
    """Return the four canonical consultation source specifications."""

    raw_dir = Path(raw_dir)

    basic_header = (
        CLASSIFICATION_COLUMN,
        BASIC_QUESTION_COLUMN,
        BASIC_ANSWER_COLUMN,
    )

    case_header = (
        CLASSIFICATION_COLUMN,
        CASE_QUESTION_COLUMN,
        CASE_ANSWER_COLUMN,
        PRIMARY_STATUTES_COLUMN,
        PRECEDENTS_COLUMN,
    )

    return (
        ConsultationSourceSpec(
            key="basic_part1",
            path=(
                raw_dir
                / "basic_qa_part1_20240731.csv"
            ),
            source_type="basic",
            classification_column=(
                CLASSIFICATION_COLUMN
            ),
            question_column=(
                BASIC_QUESTION_COLUMN
            ),
            answer_column=(
                BASIC_ANSWER_COLUMN
            ),
            expected_header=basic_header,
            expected_rows=1484,
            expected_family_rows=360,
        ),
        ConsultationSourceSpec(
            key="basic_part2",
            path=(
                raw_dir
                / "basic_qa_part2_20240731.csv"
            ),
            source_type="basic",
            classification_column=(
                CLASSIFICATION_COLUMN
            ),
            question_column=(
                BASIC_QUESTION_COLUMN
            ),
            answer_column=(
                BASIC_ANSWER_COLUMN
            ),
            expected_header=basic_header,
            expected_rows=3966,
            expected_family_rows=513,
        ),
        ConsultationSourceSpec(
            key="case_part1",
            path=(
                raw_dir
                / "case_qa_part1_20240731.csv"
            ),
            source_type="case",
            classification_column=(
                CLASSIFICATION_COLUMN
            ),
            question_column=(
                CASE_QUESTION_COLUMN
            ),
            answer_column=(
                CASE_ANSWER_COLUMN
            ),
            expected_header=(
                CLASSIFICATION_COLUMN,
                CASE_QUESTION_COLUMN,
                CASE_ANSWER_COLUMN,
            ),
            expected_rows=1938,
            expected_family_rows=792,
        ),
        ConsultationSourceSpec(
            key="case_part2",
            path=(
                raw_dir
                / "case_qa_part2_20240731.csv"
            ),
            source_type="case",
            classification_column=(
                CLASSIFICATION_COLUMN
            ),
            question_column=(
                CASE_QUESTION_COLUMN
            ),
            answer_column=(
                CASE_ANSWER_COLUMN
            ),
            expected_header=case_header,
            expected_rows=3438,
            expected_family_rows=0,
        ),
    )


def load_consultation_source(
    spec: ConsultationSourceSpec,
) -> list[RawConsultationRow]:
    """Load and validate one CP949 consultation CSV."""

    if not spec.path.is_file():
        raise FileNotFoundError(
            "Missing consultation source: "
            f"{spec.path.name}"
        )

    loaded_rows: list[
        RawConsultationRow
    ] = []

    try:
        with spec.path.open(
            "r",
            encoding="cp949",
            newline="",
        ) as handle:
            reader = csv.DictReader(handle)

            actual_header = tuple(
                reader.fieldnames or ()
            )

            if (
                actual_header
                != spec.expected_header
            ):
                raise ConsultationSourceError(
                    "Unexpected header for "
                    f"{spec.path.name}: "
                    f"{actual_header!r}"
                )

            for source_row, row in enumerate(
                reader,
                start=2,
            ):
                loaded_rows.append(
                    RawConsultationRow(
                        source_key=spec.key,
                        source_type=(
                            spec.source_type
                        ),
                        source_file=(
                            spec.path.name
                        ),
                        source_row=source_row,
                        legal_path=str(
                            row.get(
                                spec.classification_column,
                                "",
                            )
                            or ""
                        ),
                        question=str(
                            row.get(
                                spec.question_column,
                                "",
                            )
                            or ""
                        ),
                        answer=str(
                            row.get(
                                spec.answer_column,
                                "",
                            )
                            or ""
                        ),
                        primary_statutes=str(
                            row.get(
                                PRIMARY_STATUTES_COLUMN,
                                "",
                            )
                            or ""
                        ),
                        precedents=str(
                            row.get(
                                PRECEDENTS_COLUMN,
                                "",
                            )
                            or ""
                        ),
                    )
                )
    except UnicodeDecodeError as error:
        raise ConsultationSourceError(
            "CP949 decoding failed for "
            f"{spec.path.name}"
        ) from error

    if (
        len(loaded_rows)
        != spec.expected_rows
    ):
        raise ConsultationSourceError(
            "Unexpected row count for "
            f"{spec.path.name}: "
            f"{len(loaded_rows)} "
            f"!= {spec.expected_rows}"
        )

    return loaded_rows


def load_all_consultation_sources(
    raw_dir: Path,
    *,
    specs: Sequence[
        ConsultationSourceSpec
    ]
    | None = None,
) -> list[RawConsultationRow]:
    """Load consultation sources in specification order."""

    source_specs = (
        tuple(specs)
        if specs is not None
        else default_source_specs(
            Path(raw_dir)
        )
    )

    loaded_rows: list[
        RawConsultationRow
    ] = []

    for spec in source_specs:
        loaded_rows.extend(
            load_consultation_source(spec)
        )

    return loaded_rows
