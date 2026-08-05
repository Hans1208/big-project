from __future__ import annotations

import csv

from pathlib import Path

import pytest

from rag.consultation_loader import (
    ConsultationSourceError,
    ConsultationSourceSpec,
    default_source_specs,
    load_all_consultation_sources,
    load_consultation_source,
)


CLASSIFICATION = "\ubc95\ub960\ubd84\ub958"
BASIC_QUESTION = "\uae30\ubcf8\uc9c8\ubb38"
BASIC_ANSWER = "\uae30\ubcf8\ub2f5\ubcc0"
CASE_QUESTION = "\uc720\uc0ac\uc9c8\ubb38"
CASE_ANSWER = "\uc720\uc0ac\ub2f5\ubcc0"
PRIMARY_STATUTES = "\uc8fc\uc694\ubc95\ub839"
PRECEDENTS = "\ud310\ub840"


def _write_cp949_csv(
    path: Path,
    header: tuple[str, ...],
    rows: list[tuple[str, ...]],
) -> None:
    with path.open(
        "w",
        encoding="cp949",
        newline="",
    ) as handle:
        writer = csv.writer(handle)
        writer.writerow(header)
        writer.writerows(rows)


def _basic_spec(
    path: Path,
    *,
    key: str = "basic_test",
    expected_rows: int = 1,
) -> ConsultationSourceSpec:
    return ConsultationSourceSpec(
        key=key,
        path=path,
        source_type="basic",
        classification_column=(
            CLASSIFICATION
        ),
        question_column=BASIC_QUESTION,
        answer_column=BASIC_ANSWER,
        expected_header=(
            CLASSIFICATION,
            BASIC_QUESTION,
            BASIC_ANSWER,
        ),
        expected_rows=expected_rows,
        expected_family_rows=(
            expected_rows
        ),
    )


def _case_spec(
    path: Path,
    *,
    key: str = "case_test",
    expected_rows: int = 1,
) -> ConsultationSourceSpec:
    return ConsultationSourceSpec(
        key=key,
        path=path,
        source_type="case",
        classification_column=(
            CLASSIFICATION
        ),
        question_column=CASE_QUESTION,
        answer_column=CASE_ANSWER,
        expected_header=(
            CLASSIFICATION,
            CASE_QUESTION,
            CASE_ANSWER,
            PRIMARY_STATUTES,
            PRECEDENTS,
        ),
        expected_rows=expected_rows,
        expected_family_rows=(
            expected_rows
        ),
    )


def test_default_specs_match_real_source_contract(
    tmp_path: Path,
) -> None:
    specs = default_source_specs(
        tmp_path
    )

    assert [
        spec.key
        for spec in specs
    ] == [
        "basic_part1",
        "basic_part2",
        "case_part1",
        "case_part2",
    ]

    assert [
        spec.path.name
        for spec in specs
    ] == [
        "basic_qa_part1_20240731.csv",
        "basic_qa_part2_20240731.csv",
        "case_qa_part1_20240731.csv",
        "case_qa_part2_20240731.csv",
    ]

    assert [
        spec.source_type
        for spec in specs
    ] == [
        "basic",
        "basic",
        "case",
        "case",
    ]

    assert [
        spec.expected_rows
        for spec in specs
    ] == [
        1484,
        3966,
        1938,
        3438,
    ]

    assert [
        spec.expected_family_rows
        for spec in specs
    ] == [
        360,
        513,
        792,
        0,
    ]

    assert specs[0].expected_header == (
        CLASSIFICATION,
        BASIC_QUESTION,
        BASIC_ANSWER,
    )

    assert specs[3].expected_header == (
        CLASSIFICATION,
        CASE_QUESTION,
        CASE_ANSWER,
        PRIMARY_STATUTES,
        PRECEDENTS,
    )


def test_load_basic_source_reads_cp949_and_metadata(
    tmp_path: Path,
) -> None:
    source_path = (
        tmp_path / "basic.csv"
    )

    _write_cp949_csv(
        source_path,
        (
            CLASSIFICATION,
            BASIC_QUESTION,
            BASIC_ANSWER,
        ),
        [
            (
                "\uc0c1\uc18d\uacfc\uc720\uc5b8>"
                "\uc0c1\uc18d\ud3ec\uae30",
                "\uc0c1\uc18d\uc744 "
                "\ud3ec\uae30\ud558\ub824\uba74?",
                "\uac00\uc815\ubc95\uc6d0\uc5d0 "
                "\uc2e0\uace0\ud569\ub2c8\ub2e4.",
            ),
            (
                "\uce5c\uc871>\ubd80\uc591",
                "\ubd80\uc591\uc758\ubb34\uac00 "
                "\uc788\ub098\uc694?",
                "\uc694\uac74\uc5d0 \ub530\ub77c "
                "\ud310\ub2e8\ud569\ub2c8\ub2e4.",
            ),
        ],
    )

    rows = load_consultation_source(
        _basic_spec(
            source_path,
            expected_rows=2,
        )
    )

    assert len(rows) == 2

    assert rows[0].source_key == (
        "basic_test"
    )
    assert rows[0].source_type == "basic"
    assert rows[0].source_file == (
        "basic.csv"
    )
    assert rows[0].source_row == 2
    assert rows[0].legal_path == (
        "\uc0c1\uc18d\uacfc\uc720\uc5b8>"
        "\uc0c1\uc18d\ud3ec\uae30"
    )
    assert rows[0].question == (
        "\uc0c1\uc18d\uc744 "
        "\ud3ec\uae30\ud558\ub824\uba74?"
    )
    assert rows[0].answer == (
        "\uac00\uc815\ubc95\uc6d0\uc5d0 "
        "\uc2e0\uace0\ud569\ub2c8\ub2e4."
    )
    assert rows[0].primary_statutes == ""
    assert rows[0].precedents == ""

    assert rows[1].source_row == 3


def test_load_case_source_preserves_optional_fields(
    tmp_path: Path,
) -> None:
    source_path = (
        tmp_path / "case.csv"
    )

    _write_cp949_csv(
        source_path,
        (
            CLASSIFICATION,
            CASE_QUESTION,
            CASE_ANSWER,
            PRIMARY_STATUTES,
            PRECEDENTS,
        ),
        [
            (
                "\uce5c\uc871>\uc785\uc591",
                "\uc785\uc591 \uad00\uacc4\ub97c "
                "\uc885\ub8cc\ud558\uace0 "
                "\uc2f6\uc2b5\ub2c8\ub2e4.",
                "\ud30c\uc591 \uc808\ucc28\ub97c "
                "\uac80\ud1a0\ud569\ub2c8\ub2e4.",
                "\ubbfc\ubc95 \uc81c905\uc870",
                "\ub300\ubc95\uc6d0 \ud310\uacb0",
            ),
        ],
    )

    rows = load_consultation_source(
        _case_spec(source_path)
    )

    assert len(rows) == 1
    assert rows[0].source_type == "case"
    assert rows[0].primary_statutes == (
        "\ubbfc\ubc95 \uc81c905\uc870"
    )
    assert rows[0].precedents == (
        "\ub300\ubc95\uc6d0 \ud310\uacb0"
    )


def test_missing_source_reports_filename(
    tmp_path: Path,
) -> None:
    missing_path = (
        tmp_path / "missing.csv"
    )

    with pytest.raises(
        FileNotFoundError,
        match="missing.csv",
    ):
        load_consultation_source(
            _basic_spec(missing_path)
        )


def test_unexpected_header_is_rejected(
    tmp_path: Path,
) -> None:
    source_path = (
        tmp_path / "wrong-header.csv"
    )

    _write_cp949_csv(
        source_path,
        (
            CLASSIFICATION,
            BASIC_QUESTION,
            "\uc798\ubabb\ub41c\ucef8\ub7fc",
        ),
        [
            (
                "\uce5c\uc871>\ubd80\uc591",
                "\uc9c8\ubb38",
                "\ub2f5\ubcc0",
            ),
        ],
    )

    with pytest.raises(
        ConsultationSourceError,
        match=(
            "Unexpected header.*"
            "wrong-header.csv"
        ),
    ):
        load_consultation_source(
            _basic_spec(source_path)
        )


def test_invalid_cp949_is_rejected(
    tmp_path: Path,
) -> None:
    source_path = (
        tmp_path / "broken.csv"
    )

    source_path.write_bytes(
        b"\xff\xff\xff"
    )

    with pytest.raises(
        ConsultationSourceError,
        match=(
            "CP949 decoding failed.*"
            "broken.csv"
        ),
    ):
        load_consultation_source(
            _basic_spec(source_path)
        )


def test_unexpected_row_count_is_rejected(
    tmp_path: Path,
) -> None:
    source_path = (
        tmp_path / "short.csv"
    )

    _write_cp949_csv(
        source_path,
        (
            CLASSIFICATION,
            BASIC_QUESTION,
            BASIC_ANSWER,
        ),
        [
            (
                "\uce5c\uc871>\ubd80\uc591",
                "\uc9c8\ubb38",
                "\ub2f5\ubcc0",
            ),
        ],
    )

    with pytest.raises(
        ConsultationSourceError,
        match=(
            "Unexpected row count.*"
            "short.csv"
        ),
    ):
        load_consultation_source(
            _basic_spec(
                source_path,
                expected_rows=2,
            )
        )


def test_load_all_sources_preserves_spec_order(
    tmp_path: Path,
) -> None:
    first_path = tmp_path / "first.csv"
    second_path = tmp_path / "second.csv"

    header = (
        CLASSIFICATION,
        BASIC_QUESTION,
        BASIC_ANSWER,
    )

    _write_cp949_csv(
        first_path,
        header,
        [
            (
                "\uce5c\uc871>\ubd80\uc591",
                "\uccab \uc9c8\ubb38",
                "\uccab \ub2f5\ubcc0",
            ),
        ],
    )

    _write_cp949_csv(
        second_path,
        header,
        [
            (
                "\uc0c1\uc18d\uacfc\uc720\uc5b8>"
                "\uc720\uc5b8",
                "\ub458\uc9f8 \uc9c8\ubb38",
                "\ub458\uc9f8 \ub2f5\ubcc0",
            ),
        ],
    )

    rows = load_all_consultation_sources(
        tmp_path,
        specs=(
            _basic_spec(
                first_path,
                key="first",
            ),
            _basic_spec(
                second_path,
                key="second",
            ),
        ),
    )

    assert [
        row.source_key
        for row in rows
    ] == [
        "first",
        "second",
    ]
