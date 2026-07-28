import pytest

from rag.chunking import (
    chunk_document,
    chunk_documents,
)


def sample_document(content: str) -> dict:
    return {
        "document_id": "FORM-001",
        "document_type": "legal_form",
        "title": "이혼 및 재산분할청구의 소",
        "case_type": "가사소송",
        "case_subtype": "가,나,다류 가사소송",
        "content": content,
        "source": "forms/divorce-property.hwpx",
    }


def test_short_document_becomes_one_chunk():
    document = sample_document(
        "배우자와 이혼하면서 재산분할을 청구하는 서식"
    )

    chunks = chunk_document(
        document,
        chunk_size=100,
        chunk_overlap=20,
    )

    assert len(chunks) == 1

    chunk = chunks[0]

    assert chunk["chunk_id"] == "FORM-001::chunk-0000"
    assert chunk["chunk_index"] == 0
    assert chunk["document_id"] == "FORM-001"
    assert chunk["content"] == document["content"]

    assert "이혼 및 재산분할청구의 소" in (
        chunk["embedding_text"]
    )
    assert "가사소송 > 가,나,다류 가사소송" in (
        chunk["embedding_text"]
    )
    assert document["content"] in chunk["embedding_text"]


def test_long_document_is_split_with_overlap():
    first_paragraph = "가" * 60
    second_paragraph = "나" * 60
    content = (
        first_paragraph
        + "\n\n"
        + second_paragraph
    )

    chunks = chunk_document(
        sample_document(content),
        chunk_size=80,
        chunk_overlap=10,
    )

    assert len(chunks) >= 2
    assert all(
        len(chunk["content"]) <= 80
        for chunk in chunks
    )

    assert chunks[0]["content"][-10:] in (
        chunks[1]["content"]
    )

    assert [
        chunk["chunk_index"]
        for chunk in chunks
    ] == list(range(len(chunks)))

    assert len(
        {
            chunk["chunk_id"]
            for chunk in chunks
        }
    ) == len(chunks)


def test_chunk_documents_flattens_multiple_documents():
    documents = [
        sample_document("첫 번째 서식"),
        {
            **sample_document("두 번째 서식"),
            "document_id": "FORM-002",
            "title": "개명허가신청서",
        },
    ]

    chunks = chunk_documents(
        documents,
        chunk_size=100,
        chunk_overlap=20,
    )

    assert len(chunks) == 2
    assert chunks[0]["document_id"] == "FORM-001"
    assert chunks[1]["document_id"] == "FORM-002"


def test_chunk_document_rejects_invalid_overlap():
    with pytest.raises(
        ValueError,
        match="chunk_overlap",
    ):
        chunk_document(
            sample_document("테스트"),
            chunk_size=100,
            chunk_overlap=100,
        )
