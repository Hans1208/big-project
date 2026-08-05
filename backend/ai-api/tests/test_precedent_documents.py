import pytest

from rag.precedent_documents import (
    PrecedentDocumentError,
    build_precedent_chunks,
    prepare_precedent_documents,
)


def _precedent():
    return {
        "precedent_id": "300001",
        "case_name": "재산분할 등",
        "case_number": "2023드합12345",
        "decision_date": "20240115",
        "decision": "선고",
        "court_name": "서울가정법원",
        "court_type_code": "400202",
        "court_level": "LOWER",
        "case_type_name": "가사",
        "case_type_code": "400106",
        "decision_type": "판결",
        "holding": "재산분할 대상의 판단",
        "summary": "혼인 중 형성한 재산을 나눈다.",
        "referenced_statutes": "민법 제839조의2",
        "referenced_precedents": "",
        "full_text": (
            "원고와 피고는 혼인하였다. "
            "쌍방의 협력으로 재산을 형성하였다. "
            "재산분할의 비율과 방법을 정한다."
        ),
        "matched_searches": [
            "keyword:title:재산분할:lower"
        ],
        "source": "law_api:prec:300001",
    }


def test_prepare_precedent_documents_creates_sections():
    documents = prepare_precedent_documents(
        _precedent()
    )

    assert [
        document["section_type"]
        for document in documents
    ] == [
        "holding",
        "summary",
        "full_text",
    ]

    assert [
        document["document_id"]
        for document in documents
    ] == [
        "precedent:300001:holding",
        "precedent:300001:summary",
        "precedent:300001:full_text",
    ]

    assert all(
        document["document_type"]
        == "legal_precedent"
        for document in documents
    )


def test_build_precedent_chunks_adds_search_metadata():
    chunks = build_precedent_chunks(
        [_precedent()],
        chunk_size=50,
        chunk_overlap=10,
    )

    assert chunks

    assert {
        chunk["section_type"]
        for chunk in chunks
    } == {
        "holding",
        "summary",
        "full_text",
    }

    assert len(
        {
            chunk["chunk_id"]
            for chunk in chunks
        }
    ) == len(chunks)

    first = chunks[0]

    assert "사건명: 재산분할 등" in (
        first["embedding_text"]
    )
    assert "법원등급: LOWER" in (
        first["embedding_text"]
    )
    assert "참조조문: 민법 제839조의2" in (
        first["embedding_text"]
    )
    assert first["content"] in (
        first["embedding_text"]
    )


def test_prepare_precedent_documents_skips_empty_sections():
    precedent = _precedent()
    precedent["holding"] = ""
    precedent["summary"] = ""

    documents = prepare_precedent_documents(
        precedent
    )

    assert len(documents) == 1
    assert (
        documents[0]["section_type"]
        == "full_text"
    )


def test_prepare_precedent_documents_rejects_empty_case():
    with pytest.raises(
        PrecedentDocumentError,
        match="case_name",
    ):
        prepare_precedent_documents(
            {
                "precedent_id": "300001",
                "full_text": "본문",
            }
        )