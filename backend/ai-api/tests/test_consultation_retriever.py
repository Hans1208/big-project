from __future__ import annotations

import pytest

from rag.consultation_retriever import (
    ConsultationRetriever,
    infer_service_category,
    rerank_consultation_candidates,
)


class FakeEmbeddingService:
    def __init__(
        self,
        *,
        fail: bool = False,
    ):
        self.queries = []
        self.fail = fail

    def embed_query(self, query):
        self.queries.append(query)

        if self.fail:
            raise RuntimeError(
                "embedding failure"
            )

        return [1.0, 0.0]


class FakeVectorStore:
    def __init__(
        self,
        candidates=None,
        *,
        fail: bool = False,
    ):
        self.candidates = list(
            candidates or []
        )
        self.fail = fail
        self.calls = []

    def search(
        self,
        query_embedding,
        top_k,
        where=None,
    ):
        self.calls.append(
            {
                "query_embedding": (
                    query_embedding
                ),
                "top_k": top_k,
                "where": where,
            }
        )

        if self.fail:
            raise RuntimeError(
                "search failure"
            )

        return self.candidates[
            :top_k
        ]


def _candidate(
    consultation_id,
    *,
    chunk_id=None,
    source_type="case",
    service_category="inheritance",
    question="상속을 포기하고 싶어요.",
    answer="상속포기 절차를 진행합니다.",
    legal_path="상속과유언>상속포기",
    similarity=0.80,
):
    return {
        "id": (
            chunk_id
            or (
                f"consultation:"
                f"{consultation_id}"
                "::chunk-0000"
            )
        ),
        "consultation_id": (
            consultation_id
        ),
        "source_type": source_type,
        "service_category": (
            service_category
        ),
        "question": question,
        "answer": answer,
        "legal_path": legal_path,
        "source_file": "source.csv",
        "source_row": "2",
        "source_date": "2024-07-31",
        "content": answer,
        "similarity": similarity,
    }


@pytest.mark.parametrize(
    ("query", "expected"),
    (
        (
            "부모님 빚 때문에 "
            "상속을 포기하려고 합니다.",
            "inheritance",
        ),
        (
            "가족관계등록부의 "
            "출생신고를 정정하고 싶어요.",
            "family_registration",
        ),
        (
            "이혼 후 재산분할과 "
            "양육비가 궁금합니다.",
            "family_litigation",
        ),
        (
            "입양 관계를 끝내는 "
            "파양 절차가 궁금합니다.",
            "kinship",
        ),
        (
            "어떤 법률 문제인지 "
            "잘 모르겠습니다.",
            None,
        ),
    ),
)
def test_infer_service_category(
    query,
    expected,
):
    assert (
        infer_service_category(query)
        == expected
    )


def test_rerank_boosts_matching_category_and_question():
    query = (
        "부모님이 빚을 남겨 "
        "상속을 포기하고 싶습니다."
    )

    candidates = [
        _candidate(
            "consultation-litigation",
            service_category=(
                "family_litigation"
            ),
            question=(
                "이혼할 때 "
                "재산분할을 하고 싶어요."
            ),
            answer=(
                "재산분할 절차를 "
                "진행합니다."
            ),
            legal_path=(
                "친족>이혼>재산분할"
            ),
            similarity=0.84,
        ),
        _candidate(
            "consultation-inheritance",
            service_category="inheritance",
            question=(
                "부모님의 빚 때문에 "
                "상속을 포기하려고 합니다."
            ),
            answer=(
                "상속포기 또는 "
                "한정승인을 검토합니다."
            ),
            similarity=0.78,
        ),
    ]

    reranked = (
        rerank_consultation_candidates(
            query,
            candidates,
        )
    )

    assert reranked[0][
        "consultation_id"
    ] == "consultation-inheritance"

    assert reranked[0][
        "rerank_score"
    ] > reranked[1][
        "rerank_score"
    ]


def test_blank_query_returns_empty_without_embedding():
    embedding_service = (
        FakeEmbeddingService()
    )
    vector_store = FakeVectorStore()

    retriever = ConsultationRetriever(
        embedding_service=(
            embedding_service
        ),
        vector_store=vector_store,
    )

    assert retriever.retrieve("   ") == []
    assert embedding_service.queries == []
    assert vector_store.calls == []


def test_retrieve_uses_at_least_twenty_four_candidates():
    embedding_service = (
        FakeEmbeddingService()
    )
    vector_store = FakeVectorStore(
        [
            _candidate(
                "consultation-1"
            )
        ]
    )

    retriever = ConsultationRetriever(
        embedding_service=(
            embedding_service
        ),
        vector_store=vector_store,
    )

    results = retriever.retrieve(
        "상속을 포기하고 싶습니다.",
        top_k=3,
    )

    assert len(results) == 1

    assert embedding_service.queries == [
        "상속을 포기하고 싶습니다."
    ]

    assert vector_store.calls[0][
        "top_k"
    ] == 24


def test_retrieve_deduplicates_chunks_and_balances_sources():
    candidates = [
        _candidate(
            "consultation-case-1",
            chunk_id="case-1::chunk-0000",
            source_type="case",
            similarity=0.95,
        ),
        _candidate(
            "consultation-case-1",
            chunk_id="case-1::chunk-0001",
            source_type="case",
            similarity=0.94,
        ),
        _candidate(
            "consultation-case-2",
            source_type="case",
            similarity=0.93,
        ),
        _candidate(
            "consultation-case-3",
            source_type="case",
            similarity=0.92,
        ),
        _candidate(
            "consultation-basic-1",
            source_type="basic",
            similarity=0.91,
        ),
        _candidate(
            "consultation-basic-2",
            source_type="basic",
            similarity=0.90,
        ),
    ]

    retriever = ConsultationRetriever(
        embedding_service=(
            FakeEmbeddingService()
        ),
        vector_store=(
            FakeVectorStore(candidates)
        ),
    )

    results = retriever.retrieve(
        "상속을 포기하고 싶습니다.",
        top_k=3,
    )

    assert len(results) == 3

    assert len(
        {
            result[
                "consultation_id"
            ]
            for result in results
        }
    ) == 3

    assert [
        result["source_type"]
        for result in results
    ].count("case") == 2

    assert [
        result["source_type"]
        for result in results
    ].count("basic") == 1

    assert all(
        result["chunk_id"]
        for result in results
    )


def test_retrieve_fills_from_one_source_when_needed():
    candidates = [
        _candidate(
            f"consultation-case-{index}",
            source_type="case",
            similarity=(
                0.95 - index * 0.01
            ),
        )
        for index in range(4)
    ]

    retriever = ConsultationRetriever(
        embedding_service=(
            FakeEmbeddingService()
        ),
        vector_store=(
            FakeVectorStore(candidates)
        ),
    )

    results = retriever.retrieve(
        "상속 문제입니다.",
        top_k=3,
    )

    assert len(results) == 3

    assert all(
        result["source_type"]
        == "case"
        for result in results
    )


@pytest.mark.parametrize(
    "top_k",
    (
        0,
        -1,
    ),
)
def test_invalid_top_k_is_rejected(
    top_k,
):
    retriever = ConsultationRetriever(
        embedding_service=(
            FakeEmbeddingService()
        ),
        vector_store=(
            FakeVectorStore()
        ),
    )

    with pytest.raises(
        ValueError,
        match="top_k",
    ):
        retriever.retrieve(
            "상속 문제",
            top_k=top_k,
        )


def test_embedding_failure_returns_empty():
    retriever = ConsultationRetriever(
        embedding_service=(
            FakeEmbeddingService(
                fail=True
            )
        ),
        vector_store=(
            FakeVectorStore()
        ),
    )

    assert (
        retriever.retrieve(
            "상속 문제"
        )
        == []
    )


def test_vector_search_failure_returns_empty():
    retriever = ConsultationRetriever(
        embedding_service=(
            FakeEmbeddingService()
        ),
        vector_store=(
            FakeVectorStore(
                fail=True
            )
        ),
    )

    assert (
        retriever.retrieve(
            "상속 문제"
        )
        == []
    )
