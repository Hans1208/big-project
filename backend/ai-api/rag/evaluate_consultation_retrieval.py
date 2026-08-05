"""Evaluate family-law consultation retrieval quality."""

from __future__ import annotations

import json
import re

from collections import Counter
from collections.abc import (
    Callable,
    Sequence,
)
from pathlib import Path
from typing import Any

from rag.consultation_retriever import (
    retrieve_consultations,
)


EvaluationCase = dict[str, Any]

RetrieveFunction = Callable[
    ...,
    list[dict[str, Any]],
]

MINIMUM_TERM_TOP3_HITS = 10

FAMILY_CATEGORIES = {
    "family_litigation",
    "family_registration",
    "inheritance",
    "kinship",
}


EVALUATION_CASES: tuple[
    EvaluationCase,
    ...,
] = (
    {
        "name": "property_division",
        "category": "family_litigation",
        "query": (
            "\uc774\ud63c\ud558\uba74\uc11c "
            "\ud63c\uc778 \uc911 \ud568\uaed8 \ubaa8\uc740 "
            "\uc7ac\uc0b0\uc744 \ub098\ub204\uace0 "
            "\uc2f6\uc2b5\ub2c8\ub2e4."
        ),
        "expected_terms": (
            "\uc7ac\uc0b0\ubd84\ud560",
        ),
    },
    {
        "name": "child_support",
        "category": "family_litigation",
        "query": (
            "\uc804 \ubc30\uc6b0\uc790\uac00 "
            "\uc57d\uc18d\ud55c \uc591\uc721\ube44\ub97c "
            "\uacc4\uc18d \uc8fc\uc9c0 "
            "\uc54a\uc2b5\ub2c8\ub2e4."
        ),
        "expected_terms": (
            "\uc591\uc721\ube44",
        ),
    },
    {
        "name": "visitation",
        "category": "family_litigation",
        "query": (
            "\uc774\ud63c \ud6c4 "
            "\uc0c1\ub300\ubc29\uc774 "
            "\uc544\uc774\ub97c \ub9cc\ub098\uc9c0 "
            "\ubabb\ud558\uac8c \ud569\ub2c8\ub2e4."
        ),
        "expected_terms": (
            "\uba74\uc811\uad50\uc12d",
        ),
    },
    {
        "name": "register_correction",
        "category": (
            "family_registration"
        ),
        "query": (
            "\uac00\uc871\uad00\uacc4\ub4f1\ub85d\ubd80\uc5d0 "
            "\ubd80\ubaa8 \uc815\ubcf4\uac00 "
            "\uc798\ubabb\ub418\uc5b4 "
            "\uc815\uc815\ud558\uace0 "
            "\uc2f6\uc2b5\ub2c8\ub2e4."
        ),
        "expected_terms": (
            "\uac00\uc871\uad00\uacc4\ub4f1\ub85d",
            "\ub4f1\ub85d\ubd80\uc815\uc815",
        ),
    },
    {
        "name": "birth_registration",
        "category": (
            "family_registration"
        ),
        "query": (
            "\uc544\uc774\uc758 "
            "\ucd9c\uc0dd\uc2e0\uace0\uac00 "
            "\ub204\ub77d\ub410\ub294\ub370 "
            "\uc5b4\ub5bb\uac8c \ub4f1\ub85d\ud574\uc57c "
            "\ud558\ub098\uc694?"
        ),
        "expected_terms": (
            "\ucd9c\uc0dd\uc2e0\uace0",
        ),
    },
    {
        "name": "name_change",
        "category": (
            "family_registration"
        ),
        "query": (
            "\ud604\uc7ac \uc774\ub984\uc744 "
            "\ubc14\uafb8\uae30 \uc704\ud574 "
            "\uac1c\uba85 \uc2e0\uccad\uc744 "
            "\ud558\ub824\uace0 \ud569\ub2c8\ub2e4."
        ),
        "expected_terms": (
            "\uac1c\uba85",
        ),
    },
    {
        "name": "inheritance_renunciation",
        "category": "inheritance",
        "query": (
            "\ubd80\ubaa8\ub2d8\uc774 "
            "\ube5a\uc744 \ub0a8\uae30\uace0 "
            "\ub3cc\uc544\uac00\uc154\uc11c "
            "\uc0c1\uc18d\uc744 \ud3ec\uae30\ud558\uace0 "
            "\uc2f6\uc2b5\ub2c8\ub2e4."
        ),
        "expected_terms": (
            "\uc0c1\uc18d\ud3ec\uae30",
            "\ud55c\uc815\uc2b9\uc778",
        ),
    },
    {
        "name": "reserved_share",
        "category": "inheritance",
        "query": (
            "\ud615\uc81c \ud55c \uba85\uc774 "
            "\uc0c1\uc18d\uc7ac\uc0b0\uc744 "
            "\uc804\ubd80 \uac00\uc838\uac00 "
            "\uc720\ub958\ubd84\uc744 "
            "\uccad\uad6c\ud558\uace0 "
            "\uc2f6\uc2b5\ub2c8\ub2e4."
        ),
        "expected_terms": (
            "\uc720\ub958\ubd84",
        ),
    },
    {
        "name": "will_validity",
        "category": "inheritance",
        "query": (
            "\ub3cc\uc544\uac00\uc2e0 "
            "\ubd80\ubaa8\ub2d8\uc774 \ub0a8\uae34 "
            "\uc720\uc5b8\uc7a5\uc774 "
            "\ubc95\uc801\uc73c\ub85c "
            "\uc720\ud6a8\ud55c\uc9c0 "
            "\uad81\uae08\ud569\ub2c8\ub2e4."
        ),
        "expected_terms": (
            "\uc720\uc5b8",
            "\uc720\uc5b8\uc7a5",
        ),
    },
    {
        "name": "adoption_dissolution",
        "category": "kinship",
        "query": (
            "\uc591\ubd80\ubaa8\uc640\uc758 "
            "\uc785\uc591 \uad00\uacc4\ub97c "
            "\ub05d\ub0b4\ub294 \ud30c\uc591 "
            "\uc808\ucc28\uac00 "
            "\uad81\uae08\ud569\ub2c8\ub2e4."
        ),
        "expected_terms": (
            "\ud30c\uc591",
            "\uc785\uc591",
        ),
    },
    {
        "name": "parentage",
        "category": "kinship",
        "query": (
            "\ubc95\ub960\uc0c1 \uc544\ubc84\uc9c0\uac00 "
            "\uce5c\uc544\ubc84\uc9c0\uac00 \uc544\ub2c8\ub77c "
            "\uce5c\uc0dd\uc790\uad00\uacc4\ub97c "
            "\ubc14\ub85c\uc7a1\uace0 "
            "\uc2f6\uc2b5\ub2c8\ub2e4."
        ),
        "expected_terms": (
            "\uce5c\uc0dd\uc790",
            "\uce5c\uc0dd\ubd80\uc778",
            "\uce5c\uc0dd\uc790\uad00\uacc4",
        ),
    },
    {
        "name": "adult_guardianship",
        "category": "kinship",
        "query": (
            "\uce58\ub9e4\uac00 \uc2ec\ud55c "
            "\ubd80\ubaa8\ub2d8\uc744 \uc704\ud574 "
            "\uc131\ub144\ud6c4\uacac\uc744 "
            "\uc2e0\uccad\ud558\uace0 "
            "\uc2f6\uc2b5\ub2c8\ub2e4."
        ),
        "expected_terms": (
            "\uc131\ub144\ud6c4\uacac",
        ),
    },
)


class ConsultationEvaluationError(
    RuntimeError
):
    """Raised when retrieval quality gates fail."""


def _normalize_text(
    value: object,
) -> str:
    return re.sub(
        r"[^0-9a-z\uac00-\ud7a3]+",
        "",
        str(
            value or ""
        ).casefold(),
    )


def _candidate_text(
    candidate: dict[str, Any],
) -> str:
    return _normalize_text(
        " ".join(
            (
                str(
                    candidate.get(
                        "legal_path",
                        "",
                    )
                ),
                str(
                    candidate.get(
                        "question",
                        "",
                    )
                ),
                str(
                    candidate.get(
                        "answer",
                        "",
                    )
                ),
                str(
                    candidate.get(
                        "content",
                        "",
                    )
                ),
            )
        )
    )


def _gate_failures(
    report: dict[str, Any],
) -> list[str]:
    failures: list[str] = []

    query_count = int(
        report.get(
            "queries",
            0,
        )
    )

    required_term_hits = min(
        MINIMUM_TERM_TOP3_HITS,
        query_count,
    )

    if (
        report.get(
            "category_top3_hits"
        )
        != query_count
    ):
        failures.append(
            "category_top3_hits"
        )

    if int(
        report.get(
            "term_top3_hits",
            0,
        )
    ) < required_term_hits:
        failures.append(
            "term_top3_hits"
        )

    if int(
        report.get(
            "duplicate_result_cases",
            0,
        )
    ):
        failures.append(
            "duplicate_result_cases"
        )

    if int(
        report.get(
            "outside_family_noise",
            0,
        )
    ):
        failures.append(
            "outside_family_noise"
        )

    if int(
        report.get(
            "failed_queries",
            0,
        )
    ):
        failures.append(
            "failed_queries"
        )

    return failures


def evaluate_consultation_retrieval(
    *,
    cases: Sequence[
        EvaluationCase
    ] = EVALUATION_CASES,
    retrieve_function: (
        RetrieveFunction
    ) = retrieve_consultations,
    top_k: int = 3,
    candidate_k: int = 24,
) -> dict[str, Any]:
    if top_k < 1:
        raise ValueError(
            "top_k must be at least 1."
        )

    if candidate_k < top_k:
        raise ValueError(
            "candidate_k must be at least top_k."
        )

    category_hits = 0
    term_hits = 0
    duplicate_cases = 0
    outside_noise = 0
    failed_queries = 0

    category_counts: Counter[
        str
    ] = Counter()

    source_counts: Counter[
        str
    ] = Counter()

    case_reports: list[
        dict[str, Any]
    ] = []

    for case in cases:
        query = str(
            case["query"]
        )

        expected_category = str(
            case["category"]
        )

        expected_terms = tuple(
            str(term)
            for term
            in case[
                "expected_terms"
            ]
        )

        error_name = ""

        try:
            results = list(
                retrieve_function(
                    query,
                    top_k=top_k,
                    candidate_k=(
                        candidate_k
                    ),
                )
            )
        except Exception as error:
            results = []
            error_name = type(
                error
            ).__name__

        if not results:
            failed_queries += 1

        result_ids = [
            str(
                result.get(
                    "consultation_id",
                    "",
                )
            ).strip()
            for result in results
        ]

        duplicate_hit = (
            len(result_ids)
            != len(set(result_ids))
        )

        if duplicate_hit:
            duplicate_cases += 1

        category_hit = any(
            str(
                result.get(
                    "service_category",
                    "",
                )
            )
            == expected_category
            for result in results
        )

        if category_hit:
            category_hits += 1

        combined_text = "".join(
            _candidate_text(
                result
            )
            for result in results
        )

        term_hit = any(
            _normalize_text(term)
            in combined_text
            for term in expected_terms
        )

        if term_hit:
            term_hits += 1

        for result in results:
            result_category = str(
                result.get(
                    "service_category",
                    "",
                )
            ).strip()

            source_type = str(
                result.get(
                    "source_type",
                    "",
                )
            ).strip()

            category_counts[
                result_category
            ] += 1

            source_counts[
                source_type
            ] += 1

            if (
                result_category
                not in FAMILY_CATEGORIES
            ):
                outside_noise += 1

        case_reports.append(
            {
                "name": case["name"],
                "category": (
                    expected_category
                ),
                "query": query,
                "expected_terms": list(
                    expected_terms
                ),
                "category_hit": (
                    category_hit
                ),
                "term_hit": term_hit,
                "duplicate_hit": (
                    duplicate_hit
                ),
                "error": error_name,
                "results": [
                    {
                        "rank": rank,
                        "consultation_id": str(
                            result.get(
                                "consultation_id",
                                "",
                            )
                        ),
                        "source_type": str(
                            result.get(
                                "source_type",
                                "",
                            )
                        ),
                        "service_category": str(
                            result.get(
                                "service_category",
                                "",
                            )
                        ),
                        "legal_path": str(
                            result.get(
                                "legal_path",
                                "",
                            )
                        ),
                        "question": str(
                            result.get(
                                "question",
                                "",
                            )
                        ),
                        "similarity": float(
                            result.get(
                                "similarity",
                                0.0,
                            )
                            or 0.0
                        ),
                        "rerank_score": float(
                            result.get(
                                "rerank_score",
                                0.0,
                            )
                            or 0.0
                        ),
                    }
                    for rank, result
                    in enumerate(
                        results,
                        start=1,
                    )
                ],
            }
        )

    report: dict[str, Any] = {
        "queries": len(cases),
        "category_top3_hits": (
            category_hits
        ),
        "term_top3_hits": (
            term_hits
        ),
        "duplicate_result_cases": (
            duplicate_cases
        ),
        "outside_family_noise": (
            outside_noise
        ),
        "failed_queries": (
            failed_queries
        ),
        "category_counts": dict(
            sorted(
                category_counts.items()
            )
        ),
        "source_type_counts": dict(
            sorted(
                source_counts.items()
            )
        ),
        "cases": case_reports,
    }

    failures = _gate_failures(
        report
    )

    report["gate_failures"] = (
        failures
    )
    report["gates_passed"] = (
        not failures
    )

    return report


def assert_evaluation_gates(
    report: dict[str, Any],
) -> None:
    failures = _gate_failures(
        report
    )

    if failures:
        raise (
            ConsultationEvaluationError(
                "Consultation retrieval "
                "quality gates failed: "
                + ", ".join(failures)
            )
        )


def write_evaluation_report(
    report: dict[str, Any],
    path: str | Path,
) -> None:
    report_path = Path(path)

    report_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    report_path.write_text(
        json.dumps(
            report,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
        newline="\n",
    )


def main() -> None:
    report = (
        evaluate_consultation_retrieval()
    )

    assert_evaluation_gates(
        report
    )

    print(
        "Consultation retrieval "
        "evaluation passed."
    )
    print(
        "Queries:",
        report["queries"],
    )
    print(
        "Category Top-3 hits:",
        report[
            "category_top3_hits"
        ],
    )
    print(
        "Term Top-3 hits:",
        report[
            "term_top3_hits"
        ],
    )
    print(
        "Duplicate cases:",
        report[
            "duplicate_result_cases"
        ],
    )
    print(
        "Outside-family noise:",
        report[
            "outside_family_noise"
        ],
    )
    print(
        "Failed queries:",
        report[
            "failed_queries"
        ],
    )


if __name__ == "__main__":
    main()
