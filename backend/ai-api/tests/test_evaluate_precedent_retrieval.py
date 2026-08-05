from rag.evaluate_precedent_retrieval import (
    CATEGORY_MIN_TOP_5_HITS,
    EVALUATION_CASES,
    MIN_TOTAL_TOP_5_HITS,
    evaluate_precedent_retrieval,
    quality_gate_failures,
)


def test_default_evaluation_cases_cover_service_categories():
    assert len(EVALUATION_CASES) == 11

    counts = {}

    for case in EVALUATION_CASES:
        category = case["category"]
        counts[category] = (
            counts.get(category, 0)
            + 1
        )

    assert counts == {
        "family_litigation": 3,
        "family_registration": 2,
        "inheritance": 3,
        "kinship": 3,
    }

    assert MIN_TOTAL_TOP_5_HITS == 9

    assert CATEGORY_MIN_TOP_5_HITS == {
        "family_litigation": 2,
        "family_registration": 1,
        "inheritance": 2,
        "kinship": 2,
    }


def test_evaluation_counts_hits_duplicates_and_categories():
    cases = (
        {
            "name": "property",
            "category": "family_litigation",
            "query": "query-property",
            "expected_terms": (
                "\uc7ac\uc0b0\ubd84\ud560",
            ),
        },
        {
            "name": "support",
            "category": "family_litigation",
            "query": "query-support",
            "expected_terms": (
                "\uc591\uc721\ube44",
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
                    "case_name": (
                        "\uc7ac\uc0b0\ubd84\ud560"
                    ),
                    "content": "",
                }
            ]

        return [
            {
                "precedent_id": "200",
                "case_name": "\uc774\ud63c",
                "content": "",
            },
            {
                "precedent_id": "300",
                "case_name": (
                    "\uc591\uc721\ube44 "
                    "\uccad\uad6c"
                ),
                "content": "",
            },
            {
                "precedent_id": "300",
                "case_name": (
                    "\uc591\uc721\ube44 "
                    "\uccad\uad6c"
                ),
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
        "category_results": {
            "family_litigation": {
                "cases": 2,
                "top_1_hits": 1,
                "top_5_hits": 2,
            },
        },
    }


def test_quality_gate_reports_all_failures():
    passing = {
        "top_5_hits": 9,
        "duplicate_cases": 0,
        "category_results": {
            "family_litigation": {
                "top_5_hits": 2,
            },
            "family_registration": {
                "top_5_hits": 1,
            },
            "inheritance": {
                "top_5_hits": 2,
            },
            "kinship": {
                "top_5_hits": 2,
            },
        },
    }

    assert quality_gate_failures(
        passing
    ) == []

    failing = {
        "top_5_hits": 8,
        "duplicate_cases": 1,
        "category_results": {
            "family_litigation": {
                "top_5_hits": 2,
            },
            "family_registration": {
                "top_5_hits": 0,
            },
            "inheritance": {
                "top_5_hits": 2,
            },
            "kinship": {
                "top_5_hits": 1,
            },
        },
    }

    failures = quality_gate_failures(
        failing
    )

    assert len(failures) == 4

    assert any(
        "overall" in failure
        for failure in failures
    )

    assert any(
        "duplicate" in failure
        for failure in failures
    )

    assert any(
        "family_registration" in failure
        for failure in failures
    )

    assert any(
        "kinship" in failure
        for failure in failures
    )
