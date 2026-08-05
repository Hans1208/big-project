from __future__ import annotations

import json

from pathlib import Path

import pytest

from rag.consultation_loader import (
    RawConsultationRow,
)
from rag.consultation_normalizer import (
    PersonalInformationDetectedError,
    find_personal_information_candidates,
    map_service_category,
    normalize_consultations,
    normalize_text,
    write_normalized_outputs,
)


def _row(
    *,
    source_key: str = "basic_part1",
    source_type: str = "basic",
    source_file: str = "basic.csv",
    source_row: int = 2,
    legal_path: str,
    question: str,
    answer: str,
) -> RawConsultationRow:
    return RawConsultationRow(
        source_key=source_key,
        source_type=source_type,
        source_file=source_file,
        source_row=source_row,
        legal_path=legal_path,
        question=question,
        answer=answer,
    )


def test_normalize_text_removes_html_entities_and_whitespace():
    value = (
        "  <p>\uc0c1\uc18d&nbsp;"
        "<strong>\ud3ec\uae30</strong></p>\n\n"
        "\uc808\ucc28  "
    )

    assert normalize_text(value) == (
        "\uc0c1\uc18d \ud3ec\uae30 \uc808\ucc28"
    )


@pytest.mark.parametrize(
    ("legal_path", "expected"),
    (
        (
            "\uac00\uc871\uad00\uacc4\ub4f1\ub85d>"
            "\uac1c\uba85",
            "family_registration",
        ),
        (
            "\uc0c1\uc18d\uacfc\uc720\uc5b8>"
            "\uc0c1\uc18d\ud3ec\uae30",
            "inheritance",
        ),
        (
            "\uce5c\uc871>\uc774\ud63c>"
            "\uc7ac\ud310\uc0c1\uc774\ud63c",
            "family_litigation",
        ),
        (
            "\uce5c\uc871>\uc57d\ud63c\uacfc\ud63c\uc778>"
            "\uc0ac\uc2e4\ud63c",
            "family_litigation",
        ),
        (
            "\uce5c\uc871>"
            "\uc591\uc721\uad8c\uc790\uc591\uc721\ube44"
            "\uba74\uc811\uad50\uc12d\uad8c\ub4f1>"
            "\uc591\uc721\ube44",
            "family_litigation",
        ),
        (
            "\uce5c\uc871>\ubd80\ubaa8\uc640\uc790>"
            "\uce5c\uad8c>"
            "\u2161.\uce5c\uad8c\uc790"
            "(\uc9c0\uc815\uacfc\ubcc0\uacbd)",
            "family_litigation",
        ),
        (
            "\uce5c\uc871>\ubd80\ubaa8\uc640\uc790>"
            "\uc785\uc591",
            "kinship",
        ),
        (
            "\ubbfc\uc0ac>\uacc4\uc57d",
            None,
        ),
        (
            "\uac00\uc871\uad00\uacc4\ub4f1\ub85d"
            "\uc608\uaddc \uc124\uba85",
            None,
        ),
    ),
)
def test_map_service_category(
    legal_path,
    expected,
):
    assert (
        map_service_category(legal_path)
        == expected
    )


def test_normalize_filters_deduplicates_and_creates_stable_ids():
    rows = [
        _row(
            legal_path=(
                "\uc0c1\uc18d\uacfc\uc720\uc5b8>"
                "\uc0c1\uc18d\ud3ec\uae30"
            ),
            question=(
                " <p>\uc0c1\uc18d\uc744 "
                "\ud3ec\uae30\ud558\ub824\uba74?</p> "
            ),
            answer=(
                "\uac00\uc815\ubc95\uc6d0\uc5d0 "
                "\uc2e0\uace0\ud569\ub2c8\ub2e4."
                "\u203b \uc790\uc138\ud55c \uc0ac\ud56d\uc740 "
                "\ubc95\uc6d0\uc73c\ub85c "
                "\ubb38\uc758\ud558\uc2dc\uae30 "
                "\ubc14\ub78d\ub2c8\ub2e4."
            ),
        ),
        _row(
            source_key="case_part1",
            source_type="case",
            source_file="case.csv",
            source_row=3,
            legal_path=(
                "\uc0c1\uc18d\uacfc\uc720\uc5b8>"
                "\uc0c1\uc18d\ud3ec\uae30"
            ),
            question=(
                "\uc0c1\uc18d\uc744 "
                "\ud3ec\uae30\ud558\ub824\uba74?"
            ),
            answer=(
                "\uac00\uc815\ubc95\uc6d0\uc5d0 "
                "\uc2e0\uace0\ud569\ub2c8\ub2e4."
            ),
        ),
        _row(
            source_row=4,
            legal_path="\ubbfc\uc0ac>\uacc4\uc57d",
            question="\uacc4\uc57d \uc9c8\ubb38",
            answer="\uacc4\uc57d \ub2f5\ubcc0",
        ),
        _row(
            source_row=5,
            legal_path=(
                "\uce5c\uc871>\ubd80\ubaa8\uc640\uc790>"
                "\uc785\uc591"
            ),
            question=" ",
            answer="\uc785\uc591 \ub2f5\ubcc0",
        ),
    ]

    first, first_report = (
        normalize_consultations(rows)
    )
    second, second_report = (
        normalize_consultations(rows)
    )

    assert len(first) == 1
    assert first == second

    item = first[0]

    assert item.consultation_id.startswith(
        "consultation-"
    )
    assert len(item.consultation_id) == 37
    assert item.source_type == "basic"
    assert item.service_category == (
        "inheritance"
    )
    assert item.question == (
        "\uc0c1\uc18d\uc744 "
        "\ud3ec\uae30\ud558\ub824\uba74?"
    )
    assert item.answer == (
        "\uac00\uc815\ubc95\uc6d0\uc5d0 "
        "\uc2e0\uace0\ud569\ub2c8\ub2e4."
    )
    assert item.source_date == "2024-07-31"

    assert first_report == second_report
    assert first_report["input_rows"] == 4
    assert first_report[
        "family_candidate_rows"
    ] == 3
    assert first_report[
        "excluded_non_family_rows"
    ] == 1
    assert first_report[
        "excluded_blank_rows"
    ] == 1
    assert first_report[
        "duplicate_rows"
    ] == 1
    assert first_report[
        "removed_contact_footers"
    ] == 1
    assert first_report[
        "normalized_rows"
    ] == 1
    assert first_report[
        "category_counts"
    ] == {
        "inheritance": 1,
    }
    assert first_report[
        "personal_information_candidates"
    ] == []


def test_personal_information_candidates_are_masked():
    candidates = (
        find_personal_information_candidates(
            question=(
                "\uc5f0\ub77d\ucc98\ub294 "
                "010-1234-5678"
            ),
            answer=(
                "\uc774\uba54\uc77c test@example.com"
            ),
        )
    )

    assert [
        candidate["kind"]
        for candidate in candidates
    ] == [
        "phone",
        "email",
    ]

    assert all(
        "010-1234-5678"
        not in candidate["masked_value"]
        for candidate in candidates
    )

    assert all(
        "test@example.com"
        not in candidate["masked_value"]
        for candidate in candidates
    )


def test_normalization_stops_on_personal_information():
    rows = [
        _row(
            legal_path=(
                "\uce5c\uc871>\uae30\ud0c0\uce5c\uc871>"
                "\ubd80\uc591"
            ),
            question=(
                "\uc5f0\ub77d\ucc98\ub294 "
                "010-1234-5678"
            ),
            answer="\ubd80\uc591 \ub2f5\ubcc0",
        )
    ]

    with pytest.raises(
        PersonalInformationDetectedError,
    ) as caught:
        normalize_consultations(rows)

    report = caught.value.report

    assert report[
        "personal_information_candidates"
    ][0]["kind"] == "phone"
    assert report[
        "personal_information_candidates"
    ][0]["source_file"] == "basic.csv"
    assert report[
        "personal_information_candidates"
    ][0]["source_row"] == 2


def test_write_normalized_outputs_uses_utf8_jsonl(
    tmp_path: Path,
):
    rows = [
        _row(
            legal_path=(
                "\uac00\uc871\uad00\uacc4\ub4f1\ub85d>"
                "\uac1c\uba85"
            ),
            question="\uac1c\uba85\ud558\uace0 \uc2f6\uc5b4\uc694.",
            answer="\ubc95\uc6d0 \ud5c8\uac00\uac00 \ud544\uc694\ud569\ub2c8\ub2e4.",
        )
    ]

    consultations, report = (
        normalize_consultations(rows)
    )

    processed_path = (
        tmp_path / "consultations.jsonl"
    )
    report_path = (
        tmp_path / "report.json"
    )

    write_normalized_outputs(
        consultations,
        report,
        processed_path=processed_path,
        report_path=report_path,
    )

    output_rows = [
        json.loads(line)
        for line in processed_path.read_text(
            encoding="utf-8"
        ).splitlines()
    ]

    saved_report = json.loads(
        report_path.read_text(
            encoding="utf-8"
        )
    )

    assert output_rows[0]["question"] == (
        "\uac1c\uba85\ud558\uace0 \uc2f6\uc5b4\uc694."
    )
    assert saved_report["normalized_rows"] == 1
