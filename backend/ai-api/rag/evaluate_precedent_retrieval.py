"""Evaluate representative precedent retrieval queries."""

from __future__ import annotations

import re

from collections.abc import (
    Callable,
    Sequence,
)
from typing import Any

from rag.precedent_retriever import (
    retrieve_precedents,
)


EvaluationCase = dict[str, Any]

RetrieveFunction = Callable[
    [str, int],
    list[dict[str, Any]],
]


MIN_TOTAL_TOP_5_HITS = 9

CATEGORY_MIN_TOP_5_HITS = {
    "family_litigation": 2,
    "family_registration": 1,
    "inheritance": 2,
    "kinship": 2,
}


EVALUATION_CASES: tuple[
    EvaluationCase,
    ...,
] = (
    {
        "name": "property_division",
        "category": "family_litigation",
        "query": (
            "\ud63c\uc778 \uc911 "
            "\ubd80\ubd80\uac00 \ud568\uaed8 "
            "\ud615\uc131\ud55c \uc7ac\uc0b0\uc744 "
            "\uc774\ud63c\ud560 \ub54c "
            "\uc5b4\ub5bb\uac8c "
            "\ub098\ub204\ub098\uc694?"
        ),
        "expected_terms": (
            "\uc7ac\uc0b0\ubd84\ud560",
        ),
    },
    {
        "name": "child_support",
        "category": "family_litigation",
        "query": (
            "\uc774\ud63c\ud55c "
            "\uc0c1\ub300\ubc29\uc774 "
            "\uc790\ub140 \uc591\uc721\ube44\ub97c "
            "\uc9c0\uae09\ud558\uc9c0 "
            "\uc54a\uace0 \uc788\uc2b5\ub2c8\ub2e4."
        ),
        "expected_terms": (
            "\uc591\uc721\ube44",
        ),
    },
    {
        "name": "child_visitation",
        "category": "family_litigation",
        "query": (
            "\uc774\ud63c \ud6c4 "
            "\uc0c1\ub300\ubc29\uc774 "
            "\uc790\ub140\ub97c \ub9cc\ub098\uc9c0 "
            "\ubabb\ud558\uac8c \ud558\ub294\ub370 "
            "\uba74\uc811\uad50\uc12d\uc744 "
            "\uccad\uad6c\ud558\uace0 "
            "\uc2f6\uc2b5\ub2c8\ub2e4."
        ),
        "expected_terms": (
            "\uba74\uc811\uad50\uc12d",
        ),
    },
    {
        "name": (
            "family_register_"
            "parent_correction"
        ),
        "category": "family_registration",
        "query": (
            "\uac00\uc871\uad00\uacc4"
            "\ub4f1\ub85d\ubd80\uc5d0 "
            "\uc798\ubabb \uae30\ub85d\ub41c "
            "\ubd80\ubaa8 \uc815\ubcf4\ub97c "
            "\uc815\uc815\ud558\uace0 "
            "\uc2f6\uc2b5\ub2c8\ub2e4."
        ),
        "expected_terms": (
            "\uac00\uc871\uad00\uacc4"
            "\ub4f1\ub85d\ubd80\uc815\uc815",
            "\ub4f1\ub85d\ubd80\uc815\uc815",
            "\uac00\uc871\uad00\uacc4"
            "\ub4f1\ub85d",
        ),
    },
    {
        "name": "missing_birth_registration",
        "category": "family_registration",
        "query": (
            "\ucd9c\uc0dd\uc2e0\uace0\uac00 "
            "\ub204\ub77d\ub418\uc5b4 "
            "\uac00\uc871\uad00\uacc4"
            "\ub4f1\ub85d\ubd80\ub97c "
            "\ubc14\ub85c\uc7a1\uace0 "
            "\uc2f6\uc2b5\ub2c8\ub2e4."
        ),
        "expected_terms": (
            "\ucd9c\uc0dd\uc2e0\uace0",
            "\uac00\uc871\uad00\uacc4"
            "\ub4f1\ub85d\ubd80\uc815\uc815",
            "\uac00\uc871\uad00\uacc4"
            "\ub4f1\ub85d",
        ),
    },
    {
        "name": "reserved_share",
        "category": "inheritance",
        "query": (
            "\ubd80\ubaa8\uac00 "
            "\uc804 \uc7ac\uc0b0\uc744 "
            "\ud55c \uc790\ub140\uc5d0\uac8c "
            "\uc99d\uc5ec\ud574 "
            "\ub2e4\ub978 \uc0c1\uc18d\uc778\uc758 "
            "\uc0c1\uc18d\ubd84\uc774 "
            "\uce68\ud574\ub418\uc5c8\uc2b5\ub2c8\ub2e4."
        ),
        "expected_terms": (
            "\uc720\ub958\ubd84",
        ),
    },
    {
        "name": "inheritance_renunciation",
        "category": "inheritance",
        "query": (
            "\ubd80\ubaa8\uac00 "
            "\ub9ce\uc740 \ube5a\uc744 "
            "\ub0a8\uae30\uace0 \uc0ac\ub9dd\ud574 "
            "\uc0c1\uc18d\uc744 \ubc1b\uc9c0 "
            "\uc54a\uc73c\ub824\uace0 "
            "\ud569\ub2c8\ub2e4."
        ),
        "expected_terms": (
            "\uc0c1\uc18d\ud3ec\uae30",
            "\ud55c\uc815\uc2b9\uc778",
        ),
    },
    {
        "name": "will_validity",
        "category": "inheritance",
        "query": (
            "\uc0ac\ub9dd\ud55c "
            "\ubd80\ubaa8\uac00 \ub0a8\uae34 "
            "\uc720\uc5b8\uc758 \ud6a8\ub825\uc744 "
            "\ub2e4\ud22c\uace0 "
            "\uc2f6\uc2b5\ub2c8\ub2e4."
        ),
        "expected_terms": (
            "\uc720\uc5b8",
            "\uc720\uc5b8\ud6a8\ub825",
            "\uc720\uc99d",
        ),
    },
    {
        "name": "adoption_dissolution",
        "category": "kinship",
        "query": (
            "\uc591\ubd80\ubaa8\uc640\uc758 "
            "\uc785\uc591 \uad00\uacc4\ub97c "
            "\uc885\ub8cc\ud558\uace0 "
            "\uc2f6\uc2b5\ub2c8\ub2e4."
        ),
        "expected_terms": (
            "\ud30c\uc591",
            "\uc785\uc591",
        ),
    },
    {
        "name": (
            "parent_child_"
            "relationship"
        ),
        "category": "kinship",
        "query": (
            "\ubc95\ub960\uc0c1 "
            "\uc544\ubc84\uc9c0\uac00 "
            "\uce5c\uc544\ubc84\uc9c0\uac00 "
            "\uc544\ub2c8\uc5b4\uc11c "
            "\uce5c\uc0dd\uc790 \uad00\uacc4\ub97c "
            "\ub2e4\ud22c\uace0 "
            "\uc2f6\uc2b5\ub2c8\ub2e4."
        ),
        "expected_terms": (
            "\uce5c\uc0dd\ubd80\uc778",
            "\uce5c\uc0dd\uc790\uad00\uacc4"
            "\ubd80\uc874\uc7ac\ud655\uc778",
            "\uce5c\uc0dd\uc790\uad00\uacc4"
            "\uc874\ubd80\ud655\uc778",
        ),
    },
    {
        "name": "adult_guardianship",
        "category": "kinship",
        "query": (
            "\uce58\ub9e4\uac00 \uc2ec\ud55c "
            "\ubd80\ubaa8\ub97c \uc704\ud574 "
            "\uc131\ub144\ud6c4\uacac "
            "\uac1c\uc2dc\ub97c "
            "\uc2e0\uccad\ud558\uace0 "
            "\uc2f6\uc2b5\ub2c8\ub2e4."
        ),
        "expected_terms": (
            "\uc131\ub144\ud6c4\uacac",
            "\ud6c4\uacac\uac1c\uc2dc",
        ),
    },
)


def _normalize_text(
    value: object,
) -> str:
    return re.sub(
        r"[^0-9a-z\uac00-\ud7a3]+",
        "",
        str(value).casefold(),
    )


def _candidate_text(
    result: dict[str, Any],
) -> str:
    fields = (
        "case_name",
        "content",
        "holding",
        "summary",
        "referenced_statutes",
    )

    return "\n".join(
        str(
            result.get(
                field,
                "",
            )
        )
        for field in fields
    )


def _matches_expected(
    result: dict[str, Any],
    case: EvaluationCase,
) -> bool:
    normalized_candidate = (
        _normalize_text(
            _candidate_text(result)
        )
    )

    return any(
        _normalize_text(term)
        in normalized_candidate
        for term in case["expected_terms"]
    )


def evaluate_precedent_retrieval(
    *,
    cases: Sequence[
        EvaluationCase
    ] = EVALUATION_CASES,
    retrieve: RetrieveFunction = (
        retrieve_precedents
    ),
    print_results: bool = True,
) -> dict[str, Any]:
    top_1_hits = 0
    top_5_hits = 0
    duplicate_cases = 0

    category_results: dict[
        str,
        dict[str, int],
    ] = {}

    for case in cases:
        category = str(
            case["category"]
        )

        category_stats = (
            category_results.setdefault(
                category,
                {
                    "cases": 0,
                    "top_1_hits": 0,
                    "top_5_hits": 0,
                },
            )
        )

        category_stats["cases"] += 1

        results = retrieve(
            case["query"],
            top_k=5,
        )

        expected_ranks = [
            rank
            for rank, result in enumerate(
                results,
                start=1,
            )
            if _matches_expected(
                result,
                case,
            )
        ]

        expected_rank = (
            expected_ranks[0]
            if expected_ranks
            else None
        )

        if expected_rank == 1:
            top_1_hits += 1
            category_stats[
                "top_1_hits"
            ] += 1

        if (
            expected_rank is not None
            and expected_rank <= 5
        ):
            top_5_hits += 1
            category_stats[
                "top_5_hits"
            ] += 1

        result_ids = [
            str(
                result.get(
                    "precedent_id",
                    result.get(
                        "id",
                        "",
                    ),
                )
            ).strip()
            for result in results
        ]

        result_ids = [
            result_id
            for result_id in result_ids
            if result_id
        ]

        if (
            len(result_ids)
            != len(set(result_ids))
        ):
            duplicate_cases += 1

        if not print_results:
            continue

        print("=" * 70)
        print("CASE:", case["name"])
        print("CATEGORY:", category)
        print(
            "EXPECTED TERMS:",
            ", ".join(
                case["expected_terms"]
            ),
        )
        print(
            "EXPECTED RANK:",
            expected_rank,
        )

        for rank, result in enumerate(
            results,
            start=1,
        ):
            print(
                rank,
                result.get(
                    "precedent_id",
                    "",
                ),
                result.get(
                    "case_name",
                    "",
                ),
                result.get(
                    "court_name",
                    "",
                ),
                result.get(
                    "decision_date",
                    "",
                ),
                result.get(
                    "section_type",
                    "",
                ),
                "similarity=",
                round(
                    float(
                        result.get(
                            "similarity",
                            0.0,
                        )
                    ),
                    4,
                ),
                "rerank=",
                round(
                    float(
                        result.get(
                            "rerank_score",
                            0.0,
                        )
                    ),
                    4,
                ),
            )

    evaluation = {
        "cases": len(cases),
        "top_1_hits": top_1_hits,
        "top_5_hits": top_5_hits,
        "duplicate_cases": (
            duplicate_cases
        ),
        "category_results": (
            category_results
        ),
    }

    if print_results:
        print()
        print(
            "=== Precedent retrieval "
            "evaluation ==="
        )
        print(
            "Cases:",
            evaluation["cases"],
        )
        print(
            "Top-1 hits:",
            evaluation["top_1_hits"],
        )
        print(
            "Top-5 hits:",
            evaluation["top_5_hits"],
        )
        print(
            "Duplicate result cases:",
            evaluation[
                "duplicate_cases"
            ],
        )

        for (
            category,
            stats,
        ) in category_results.items():
            print(
                "Category:",
                category,
                (
                    "top1="
                    f"{stats['top_1_hits']}/"
                    f"{stats['cases']}"
                ),
                (
                    "top5="
                    f"{stats['top_5_hits']}/"
                    f"{stats['cases']}"
                ),
            )

    return evaluation


def quality_gate_failures(
    result: dict[str, Any],
) -> list[str]:
    failures: list[str] = []

    overall_hits = int(
        result.get(
            "top_5_hits",
            0,
        )
    )

    if overall_hits < MIN_TOTAL_TOP_5_HITS:
        failures.append(
            "overall top-5 hits: "
            f"{overall_hits}/"
            f"{MIN_TOTAL_TOP_5_HITS}"
        )

    duplicate_cases = int(
        result.get(
            "duplicate_cases",
            0,
        )
    )

    if duplicate_cases != 0:
        failures.append(
            "duplicate cases: "
            f"{duplicate_cases}"
        )

    category_results = result.get(
        "category_results",
        {},
    )

    for (
        category,
        minimum_hits,
    ) in CATEGORY_MIN_TOP_5_HITS.items():
        category_hits = int(
            category_results
            .get(category, {})
            .get(
                "top_5_hits",
                0,
            )
        )

        if category_hits < minimum_hits:
            failures.append(
                f"{category} top-5 hits: "
                f"{category_hits}/"
                f"{minimum_hits}"
            )

    return failures


def main() -> None:
    result = (
        evaluate_precedent_retrieval()
    )

    failures = quality_gate_failures(
        result
    )

    if failures:
        print("Quality gate: FAIL")

        for failure in failures:
            print("-", failure)

        raise SystemExit(1)

    print("Quality gate: PASS")


if __name__ == "__main__":
    main()
