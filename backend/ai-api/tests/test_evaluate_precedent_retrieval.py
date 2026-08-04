from rag.evaluate_precedent_retrieval import (
    evaluate_precedent_retrieval,
)


def test_evaluation_counts_hits_and_duplicates():
    cases = (
        {
            "name": "property",
            "query": "query-property",
            "expected_terms": (
                "재산분할",
            ),
        },
        {
            "name": "support",
            "query": "query-support",
            "expected_terms": (
                "양육비",
            ),
        },
    )

    def fake_retrieve(
        query,
        *,
        top_k,
    ):
        assert top_k == 5

        if query == "query-property":
            return [
                {
                    "precedent_id": "100",
                    "case_name": "재산분할",
                    "content": "",
                }
            ]

        return [
            {
                "precedent_id": "200",
                "case_name": "이혼",
                "content": "",
            },
            {
                "precedent_id": "300",
                "case_name": "양육비 청구",
                "content": "",
            },
            {
                "precedent_id": "300",
                "case_name": "양육비 청구",
                "content": "",
            },
        ]

    result = evaluate_precedent_retrieval(
        cases=cases,
        retrieve=fake_retrieve,
        print_results=False,
    )

    assert result == {
        "cases": 2,
        "top_1_hits": 1,
        "top_5_hits": 2,
        "duplicate_cases": 1,
    }