"""Evaluate representative precedent retrieval queries."""

from __future__ import annotations

import re
from collections.abc import Callable, Sequence
from typing import Any

from rag.precedent_retriever import (
    retrieve_precedents,
)


EvaluationCase = dict[str, Any]
RetrieveFunction = Callable[
    [str, int],
    list[dict[str, Any]],
]


EVALUATION_CASES: tuple[
    EvaluationCase,
    ...,
] = (
    {
        "name": "property_division",
        "query": (
            "혼인 중 부부가 함께 형성한 재산을 "
            "이혼할 때 어떻게 나누나요?"
        ),
        "expected_terms": (
            "재산분할",
        ),
    },
    {
        "name": "child_support",
        "query": (
            "이혼한 상대방이 자녀 양육비를 "
            "지급하지 않고 있습니다."
        ),
        "expected_terms": (
            "양육비",
        ),
    },
    {
        "name": "child_visitation",
        "query": (
            "이혼 후 상대방이 자녀를 만나지 "
            "못하게 하는데 면접교섭을 청구하고 싶습니다."
        ),
        "expected_terms": (
            "면접교섭",
        ),
    },
    {
        "name": "reserved_share",
        "query": (
            "부모가 전 재산을 한 자녀에게 증여해 "
            "다른 상속인의 상속분이 침해되었습니다."
        ),
        "expected_terms": (
            "유류분",
        ),
    },
    {
        "name": "inheritance_renunciation",
        "query": (
            "부모가 많은 빚을 남기고 사망해 "
            "상속을 받지 않으려고 합니다."
        ),
        "expected_terms": (
            "상속포기",
            "한정승인",
        ),
    },
)


def _normalize_text(
    value: object,
) -> str:
    return re.sub(
        r"[^0-9a-z가-힣]+",
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
) -> dict[str, int]:
    top_1_hits = 0
    top_5_hits = 0
    duplicate_cases = 0

    for case in cases:
        results = retrieve(
            case["query"],
            5,
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

        if (
            expected_rank is not None
            and expected_rank <= 5
        ):
            top_5_hits += 1

        result_ids = [
            str(
                result.get(
                    "precedent_id",
                    result.get("id", ""),
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
        "duplicate_cases": duplicate_cases,
    }

    if print_results:
        print()
        print(
            "=== Precedent retrieval evaluation ==="
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

    return evaluation


def main() -> None:
    result = evaluate_precedent_retrieval()

    minimum_top_5_hits = max(
        1,
        (
            result["cases"] * 4 + 4
        ) // 5,
    )

    if result["duplicate_cases"]:
        raise SystemExit(
            "Duplicate precedents were returned."
        )

    if (
        result["top_5_hits"]
        < minimum_top_5_hits
    ):
        raise SystemExit(
            "Precedent Top-5 hit rate "
            "is below 80 percent."
        )


if __name__ == "__main__":
    main()