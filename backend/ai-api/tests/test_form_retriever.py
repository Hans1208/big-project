import pytest

from rag.classification import build_where_filter
from rag.form_retriever import (
    FormRetriever,
    build_filter_chain,
)


class FakeEmbeddingService:
    def __init__(self):
        self.queries = []

    def embed_query(self, query):
        self.queries.append(query)
        return [1.0, 0.0]


class FakeVectorStore:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def search(
        self,
        query_embedding,
        top_k=3,
        where=None,
    ):
        self.calls.append(
            {
                "query_embedding": query_embedding,
                "top_k": top_k,
                "where": where,
            }
        )

        if not self.responses:
            return []

        return self.responses.pop(0)


def make_result(
    chunk_id,
    document_id,
    similarity,
):
    return {
        "id": chunk_id,
        "document_id": document_id,
        "title": f"Form {document_id}",
        "case_type": "가사소송",
        "case_subtype": "가,나,다류 가사소송",
        "similarity": similarity,
        "distance": 1.0 - similarity,
        "content": "Form content",
        "source": "forms/test.hwpx",
    }


def test_build_filter_chain_uses_high_confidence_fallbacks():
    filters = build_filter_chain(
        case_type="가사소송",
        case_subtype="가,나,다류 가사소송",
        classification_confidence=0.91,
    )

    assert filters == [
        build_where_filter(
            case_type="가사소송",
            case_subtype="가,나,다류 가사소송",
        ),
        build_where_filter(
            case_type="가사소송",
        ),
        None,
    ]


def test_retrieve_deduplicates_forms_and_fills_from_fallback():
    embedding_service = FakeEmbeddingService()

    vector_store = FakeVectorStore(
        responses=[
            [
                make_result("A-0", "A", 0.95),
                make_result("A-1", "A", 0.94),
            ],
            [
                make_result("A-2", "A", 0.93),
                make_result("B-0", "B", 0.90),
            ],
        ]
    )

    retriever = FormRetriever(
        embedding_service=embedding_service,
        vector_store=vector_store,
    )

    results = retriever.retrieve(
        query="divorce property division",
        case_type="가사소송",
        case_subtype="가,나,다류 가사소송",
        classification_confidence=0.91,
        top_k=2,
    )

    assert [
        result["document_id"]
        for result in results
    ] == ["A", "B"]

    assert [
        result["chunk_id"]
        for result in results
    ] == ["A-0", "B-0"]

    assert embedding_service.queries == [
        "divorce property division"
    ]

    assert [
        call["where"]
        for call in vector_store.calls
    ] == [
        build_where_filter(
            case_type="가사소송",
            case_subtype="가,나,다류 가사소송",
        ),
        build_where_filter(
            case_type="가사소송",
        ),
    ]


def test_medium_confidence_falls_back_to_unfiltered_search():
    vector_store = FakeVectorStore(
        responses=[
            [],
            [
                make_result("C-0", "C", 0.80),
            ],
        ]
    )

    retriever = FormRetriever(
        embedding_service=FakeEmbeddingService(),
        vector_store=vector_store,
    )

    results = retriever.retrieve(
        query="legal consultation",
        case_type="상속",
        classification_confidence=0.60,
        top_k=1,
    )

    assert results[0]["document_id"] == "C"

    assert [
        call["where"]
        for call in vector_store.calls
    ] == [
        build_where_filter(
            case_type="상속",
        ),
        None,
    ]


def test_low_confidence_uses_only_unfiltered_search():
    vector_store = FakeVectorStore(
        responses=[
            [
                make_result("D-0", "D", 0.75),
            ],
        ]
    )

    retriever = FormRetriever(
        embedding_service=FakeEmbeddingService(),
        vector_store=vector_store,
    )

    retriever.retrieve(
        query="legal consultation",
        case_type="상속",
        classification_confidence=0.20,
        top_k=1,
    )

    assert len(vector_store.calls) == 1
    assert vector_store.calls[0]["where"] is None


def test_retrieve_rejects_empty_query():
    retriever = FormRetriever(
        embedding_service=FakeEmbeddingService(),
        vector_store=FakeVectorStore([]),
    )

    with pytest.raises(
        ValueError,
        match="query",
    ):
        retriever.retrieve(
            query="   ",
        )


def test_retrieve_rejects_invalid_top_k():
    retriever = FormRetriever(
        embedding_service=FakeEmbeddingService(),
        vector_store=FakeVectorStore([]),
    )

    with pytest.raises(
        ValueError,
        match="top_k",
    ):
        retriever.retrieve(
            query="consultation",
            top_k=0,
        )

