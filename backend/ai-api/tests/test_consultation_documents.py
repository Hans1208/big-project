from __future__ import annotations

from dataclasses import replace

import pytest

from rag.consultation_documents import (
    ConsultationDocumentError,
    build_consultation_chunks,
    prepare_consultation_document,
)
from rag.consultation_normalizer import (
    NormalizedConsultation,
)


def _consultation(
    **changes,
) -> NormalizedConsultation:
    consultation = NormalizedConsultation(
        consultation_id=(
            "consultation-"
            "0123456789abcdef01234567"
        ),
        source_type="case",
        service_category="inheritance",
        legal_path=(
            "\uc0c1\uc18d\uacfc\uc720\uc5b8>"
            "\uc0c1\uc18d\ud3ec\uae30"
        ),
        question=(
            "\ubd80\ubaa8\ub2d8\uc774 "
            "\ube5a\uc744 \ub0a8\uae30\uace0 "
            "\uc0ac\ub9dd\ud588\uc2b5\ub2c8\ub2e4."
        ),
        answer=(
            "\uc0c1\uc18d\uac1c\uc2dc\ub97c "
            "\uc548 \ub0a0\ubd80\ud130 "
            "3\uac1c\uc6d4 \uc548\uc5d0 "
            "\uac00\uc815\ubc95\uc6d0\uc5d0 "
            "\uc0c1\uc18d\ud3ec\uae30\ub97c "
            "\uc2e0\uace0\ud560 \uc218 "
            "\uc788\uc2b5\ub2c8\ub2e4."
        ),
        source_file=(
            "case_qa_part1_20240731.csv"
        ),
        source_row=42,
        source_date="2024-07-31",
    )

    return replace(
        consultation,
        **changes,
    )


def test_prepare_document_preserves_search_metadata():
    consultation = _consultation()

    document = (
        prepare_consultation_document(
            consultation
        )
    )

    assert document["document_id"] == (
        "consultation:"
        + consultation.consultation_id
    )
    assert document["document_type"] == (
        "legal_consultation"
    )
    assert document["title"] == (
        consultation.question
    )
    assert document["content"] == (
        consultation.answer
    )
    assert document["case_type"] == (
        "inheritance"
    )
    assert document["case_subtype"] == "case"
    assert document["consultation_id"] == (
        consultation.consultation_id
    )
    assert document["source_type"] == "case"
    assert document["service_category"] == (
        "inheritance"
    )
    assert document["legal_path"] == (
        consultation.legal_path
    )
    assert document["question"] == (
        consultation.question
    )
    assert document["answer"] == (
        consultation.answer
    )
    assert document["source_file"] == (
        consultation.source_file
    )
    assert document["source_row"] == 42
    assert document["source_date"] == (
        "2024-07-31"
    )


@pytest.mark.parametrize(
    "field_name",
    (
        "consultation_id",
        "service_category",
        "legal_path",
        "question",
        "answer",
    ),
)
def test_prepare_document_rejects_empty_required_fields(
    field_name,
):
    consultation = _consultation(
        **{field_name: ""}
    )

    with pytest.raises(
        ConsultationDocumentError,
        match=field_name,
    ):
        prepare_consultation_document(
            consultation
        )


def test_short_answer_creates_one_search_chunk():
    consultation = _consultation()

    chunks = build_consultation_chunks(
        [consultation]
    )

    assert len(chunks) == 1

    chunk = chunks[0]

    assert chunk["chunk_id"] == (
        "consultation:"
        + consultation.consultation_id
        + "::chunk-0000"
    )
    assert chunk["chunk_index"] == 0
    assert chunk["content"] == (
        consultation.answer
    )

    assert chunk["embedding_text"] == (
        "\ubd84\ub958: "
        + consultation.legal_path
        + "\n\uc9c8\ubb38: "
        + consultation.question
        + "\n\ub2f5\ubcc0: "
        + consultation.answer
    )

    assert not chunk[
        "embedding_text"
    ].startswith("passage:")


def test_question_and_category_repeat_in_every_chunk():
    answer = "".join(
        f"{index:04d}"
        for index in range(400)
    )

    consultation = _consultation(
        answer=answer
    )

    chunks = build_consultation_chunks(
        [consultation]
    )

    assert len(chunks) == 3
    assert len(chunks[0]["content"]) == 800
    assert len(chunks[1]["content"]) == 800

    assert (
        chunks[0]["content"][-120:]
        == chunks[1]["content"][:120]
    )

    assert (
        chunks[1]["content"][-120:]
        == chunks[2]["content"][:120]
    )

    for chunk in chunks:
        assert (
            f"\ubd84\ub958: "
            f"{consultation.legal_path}"
            in chunk["embedding_text"]
        )
        assert (
            f"\uc9c8\ubb38: "
            f"{consultation.question}"
            in chunk["embedding_text"]
        )
        assert (
            f"\ub2f5\ubcc0: "
            f"{chunk['content']}"
            in chunk["embedding_text"]
        )


def test_custom_chunk_size_and_overlap_are_used():
    consultation = _consultation(
        answer="A" * 250
    )

    chunks = build_consultation_chunks(
        [consultation],
        chunk_size=100,
        chunk_overlap=20,
    )

    assert [
        len(chunk["content"])
        for chunk in chunks
    ] == [
        100,
        100,
        90,
    ]

    assert (
        chunks[0]["content"][-20:]
        == chunks[1]["content"][:20]
    )


def test_multiple_consultations_create_unique_chunk_ids():
    first = _consultation()

    second = _consultation(
        consultation_id=(
            "consultation-"
            "fedcba9876543210fedcba98"
        ),
        question=(
            "\uc720\uc5b8\uc7a5\uc758 "
            "\ud6a8\ub825\uc774 "
            "\uad81\uae08\ud569\ub2c8\ub2e4."
        ),
        answer=(
            "\uc720\uc5b8\uc740 "
            "\ubc95\uc815 \ubc29\uc2dd\uc744 "
            "\uc900\uc218\ud574\uc57c "
            "\ud569\ub2c8\ub2e4."
        ),
    )

    chunks = build_consultation_chunks(
        [
            first,
            second,
        ]
    )

    chunk_ids = [
        chunk["chunk_id"]
        for chunk in chunks
    ]

    assert len(chunk_ids) == 2
    assert len(set(chunk_ids)) == 2
    assert all(
        chunk["content"]
        for chunk in chunks
    )
