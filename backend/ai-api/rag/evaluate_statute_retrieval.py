"""Evaluate representative statute retrieval queries."""

from __future__ import annotations

from typing import Any

from rag.statute_retriever import (
    retrieve_statutes,
)


EVALUATION_CASES: tuple[
    dict[str, str],
    ...,
] = (
    {
        "name": "property_division",
        "query": (
            "\uc774\ud63c\ud55c \ud6c4 "
            "\uc7ac\uc0b0\ubd84\ud560\uc744 "
            "\uccad\uad6c\ud560 \uc218 \uc788\ub294 "
            "\uae30\uac04\uc740 \uc5bc\ub9c8\uc778\uac00\uc694?"
        ),
        "law_name": "\ubbfc\ubc95",
        "article_label": "\uc81c839\uc870\uc7582",
    },
    {
        "name": "child_visitation",
        "query": (
            "\uc774\ud63c\ud55c \ud6c4 "
            "\uc790\ub140\ub97c \ub9cc\ub098\ub294 "
            "\uba74\uc811\uad50\uc12d\uad8c\uc5d0 "
            "\uad00\ud55c \ubc95\ub839\uc744 "
            "\ucc3e\uc544\uc8fc\uc138\uc694."
        ),
        "law_name": "\ubbfc\ubc95",
        "article_label": "\uc81c837\uc870\uc7582",
    },
    {
        "name": "inheritance_order",
        "query": (
            "\ubd80\ubaa8\ub2d8\uc774 "
            "\uc0ac\ub9dd\ud558\uc168\uc744 \ub54c "
            "\uc0c1\uc18d\uc778\uc758 \uc21c\uc704\ub294 "
            "\uc5b4\ub5bb\uac8c \ub418\ub098\uc694?"
        ),
        "law_name": "\ubbfc\ubc95",
        "article_label": "\uc81c1000\uc870",
    },
    {
        "name": "spouse_inheritance",
        "query": (
            "\ubc30\uc6b0\uc790\uc758 "
            "\uc0c1\uc18d \uc21c\uc704\uc640 "
            "\uc9c1\uacc4\ube44\uc18d\uacfc\uc758 "
            "\uad00\uacc4\ub97c \uc54c\ub824\uc8fc\uc138\uc694."
        ),
        "law_name": "\ubbfc\ubc95",
        "article_label": "\uc81c1003\uc870",
    },
    {
        "name": "property_inquiry",
        "query": (
            "\uac00\uc815\ubc95\uc6d0\uc774 "
            "\ub2f9\uc0ac\uc790\uc758 \uc7ac\uc0b0\uc744 "
            "\uc870\ud68c\ud560 \uc218 \uc788\ub294 "
            "\uc870\ubb38\uc744 \ucc3e\uc544\uc8fc\uc138\uc694."
        ),
        "law_name": "\uac00\uc0ac\uc18c\uc1a1\ubc95",
        "article_label": "\uc81c48\uc870\uc7583",
    },
)


def _matches_expected(
    result: dict[str, Any],
    case: dict[str, str],
) -> bool:
    return (
        str(
            result.get("law_name", "")
        ).strip()
        == case["law_name"]
        and str(
            result.get(
                "article_label",
                "",
            )
        ).strip()
        == case["article_label"]
    )


def evaluate_statute_retrieval() -> dict[str, int]:
    top_1_hits = 0
    top_3_hits = 0

    for case in EVALUATION_CASES:
        results = retrieve_statutes(
            query=case["query"],
            top_k=3,
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
            and expected_rank <= 3
        ):
            top_3_hits += 1

        print("=" * 70)
        print("CASE:", case["name"])
        print(
            "EXPECTED:",
            case["law_name"],
            case["article_label"],
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
                result.get("law_name", ""),
                result.get("article_label", ""),
                result.get("article_title", ""),
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

    result = {
        "cases": len(EVALUATION_CASES),
        "top_1_hits": top_1_hits,
        "top_3_hits": top_3_hits,
    }

    print()
    print("=== Statute retrieval evaluation ===")
    print("Cases:", result["cases"])
    print("Top-1 hits:", result["top_1_hits"])
    print("Top-3 hits:", result["top_3_hits"])

    return result


def main() -> None:
    result = evaluate_statute_retrieval()

    if result["top_3_hits"] != result["cases"]:
        raise SystemExit(
            "Some expected statutes were not in Top-3."
        )


if __name__ == "__main__":
    main()
