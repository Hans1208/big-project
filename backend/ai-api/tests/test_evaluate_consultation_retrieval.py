from __future__ import annotations

import pytest

from rag.evaluate_consultation_retrieval import (
    EVALUATION_CASES,
    ConsultationEvaluationError,
    assert_evaluation_gates,
    evaluate_consultation_retrieval,
)


def test_evaluation_passes_all_quality_gates():
    cases_by_query = {
        case["query"]: case
        for case in EVALUATION_CASES
    }

    def fake_retrieve(
        query,
        top_k=3,
        candidate_k=24,
    ):
        assert top_k == 3
        assert candidate_k == 24

        case = cases_by_query[query]
        expected_term = (
            case["expected_terms"][0]
        )
        category = case["category"]
        name = case["name"]

        return [
            {
                "consultation_id": (
                    f"{name}-case-1"
                ),
                "source_type": "case",
                "service_category": category,
                "legal_path": category,
                "question": expected_term,
                "answer": expected_term,
                "content": expected_term,
                "similarity": 0.90,
                "rerank_score": 1.10,
            },
            {
                "consultation_id": (
                    f"{name}-basic-1"
                ),
                "source_type": "basic",
                "service_category": category,
                "legal_path": category,
                "question": "기본 질문",
                "answer": "기본 답변",
                "content": "기본 답변",
                "similarity": 0.80,
                "rerank_score": 1.00,
            },
            {
                "consultation_id": (
                    f"{name}-case-2"
                ),
                "source_type": "case",
                "service_category": category,
                "legal_path": category,
                "question": "사례 질문",
                "answer": "사례 답변",
                "content": "사례 답변",
                "similarity": 0.70,
                "rerank_score": 0.90,
            },
        ]

    report = (
        evaluate_consultation_retrieval(
            retrieve_function=(
                fake_retrieve
            )
        )
    )

    assert report["queries"] == 12
    assert (
        report["category_top3_hits"]
        == 12
    )
    assert (
        report["term_top3_hits"]
        == 12
    )
    assert (
        report[
            "duplicate_result_cases"
        ]
        == 0
    )
    assert (
        report["outside_family_noise"]
        == 0
    )
    assert (
        report["failed_queries"]
        == 0
    )
    assert report["gates_passed"] is True

    assert_evaluation_gates(
        report
    )


def test_evaluation_detects_bad_results():
    cases = (
        {
            "name": "bad_case",
            "category": "inheritance",
            "query": "상속포기 문의",
            "expected_terms": (
                "상속포기",
            ),
        },
    )

    def fake_retrieve(
        query,
        top_k=3,
        candidate_k=24,
    ):
        return [
            {
                "consultation_id": "same-id",
                "source_type": "case",
                "service_category": "civil",
                "question": "계약 문제",
                "answer": "계약 답변",
                "legal_path": "민사>계약",
            },
            {
                "consultation_id": "same-id",
                "source_type": "basic",
                "service_category": "civil",
                "question": "다른 계약 문제",
                "answer": "다른 계약 답변",
                "legal_path": "민사>계약",
            },
        ]

    report = (
        evaluate_consultation_retrieval(
            cases=cases,
            retrieve_function=(
                fake_retrieve
            ),
        )
    )

    assert (
        report["category_top3_hits"]
        == 0
    )
    assert (
        report["term_top3_hits"]
        == 0
    )
    assert (
        report[
            "duplicate_result_cases"
        ]
        == 1
    )
    assert (
        report["outside_family_noise"]
        == 2
    )
    assert report["gates_passed"] is False

    with pytest.raises(
        ConsultationEvaluationError,
    ):
        assert_evaluation_gates(
            report
        )


def test_empty_result_is_counted_as_failure():
    cases = (
        {
            "name": "empty_case",
            "category": "kinship",
            "query": "성년후견 문의",
            "expected_terms": (
                "성년후견",
            ),
        },
    )

    report = (
        evaluate_consultation_retrieval(
            cases=cases,
            retrieve_function=(
                lambda *args, **kwargs: []
            ),
        )
    )

    assert (
        report["failed_queries"]
        == 1
    )
    assert report["gates_passed"] is False
