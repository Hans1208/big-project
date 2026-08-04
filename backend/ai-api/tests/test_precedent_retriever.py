from rag.precedent_retriever import (
    PrecedentRetriever,
    rerank_precedent_candidates,
)


class FakeEmbeddingService:
    def __init__(self):
        self.queries = []

    def embed_query(self, text):
        self.queries.append(text)
        return [1.0, 0.0]


class FakeVectorStore:
    def __init__(self, candidates):
        self.candidates = candidates
        self.calls = []

    def search(
        self,
        query_embedding,
        top_k,
        where=None,
    ):
        self.calls.append(
            {
                "query_embedding": query_embedding,
                "top_k": top_k,
                "where": where,
            }
        )

        return self.candidates


def _candidate(
    *,
    record_id,
    precedent_id,
    case_name,
    similarity,
    section_type,
    court_level,
):
    return {
        "id": record_id,
        "document_id": (
            f"precedent:{precedent_id}:"
            f"{section_type}"
        ),
        "precedent_id": precedent_id,
        "case_name": case_name,
        "case_number": f"case-{precedent_id}",
        "decision_date": "20240101",
        "court_name": "테스트법원",
        "court_level": court_level,
        "section_type": section_type,
        "section_label": section_type,
        "referenced_statutes": (
            "민법 제839조의2"
        ),
        "content": f"{section_type} 내용",
        "similarity": similarity,
    }


def test_reranker_prefers_title_and_holding_match():
    candidates = [
        _candidate(
            record_id="100-full",
            precedent_id="100",
            case_name="재산분할",
            similarity=0.75,
            section_type="full_text",
            court_level="LOWER",
        ),
        _candidate(
            record_id="100-holding",
            precedent_id="100",
            case_name="재산분할",
            similarity=0.70,
            section_type="holding",
            court_level="LOWER",
        ),
        _candidate(
            record_id="200-summary",
            precedent_id="200",
            case_name="양육비",
            similarity=0.80,
            section_type="summary",
            court_level="SUPREME",
        ),
    ]

    result = rerank_precedent_candidates(
        query="재산분할",
        candidates=candidates,
    )

    assert result[0]["id"] == "100-holding"
    assert result[0]["rerank_score"] > (
        result[1]["rerank_score"]
    )


def test_retriever_deduplicates_by_precedent_id():
    candidates = [
        _candidate(
            record_id="100-full",
            precedent_id="100",
            case_name="재산분할",
            similarity=0.75,
            section_type="full_text",
            court_level="LOWER",
        ),
        _candidate(
            record_id="100-holding",
            precedent_id="100",
            case_name="재산분할",
            similarity=0.70,
            section_type="holding",
            court_level="LOWER",
        ),
        _candidate(
            record_id="200-summary",
            precedent_id="200",
            case_name="양육비",
            similarity=0.80,
            section_type="summary",
            court_level="SUPREME",
        ),
    ]

    embedding_service = FakeEmbeddingService()
    vector_store = FakeVectorStore(candidates)

    retriever = PrecedentRetriever(
        embedding_service=embedding_service,
        vector_store=vector_store,
    )

    result = retriever.retrieve(
        query="재산분할",
        court_level="LOWER",
        top_k=2,
    )

    assert embedding_service.queries == [
        "재산분할"
    ]

    assert vector_store.calls[0]["where"] == {
        "court_level": "LOWER",
    }

    assert len(result) == 2

    assert [
        item["precedent_id"]
        for item in result
    ] == [
        "100",
        "200",
    ]

    assert result[0]["section_type"] == (
        "holding"
    )


def test_retriever_rejects_empty_query():
    retriever = PrecedentRetriever(
        embedding_service=FakeEmbeddingService(),
        vector_store=FakeVectorStore([]),
    )

    try:
        retriever.retrieve(query=" ")
    except ValueError as error:
        assert "query" in str(error)
    else:
        raise AssertionError(
            "ValueError was not raised."
        )