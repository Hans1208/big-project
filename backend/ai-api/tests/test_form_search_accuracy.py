from __future__ import annotations

from typing import Any

from app.ai.forms.rag_candidates import (
    search_rag_candidates,
)


SEARCH_CASES: list[dict[str, Any]] = [
    {
        "label": "\uc774\ud63c \uc7ac\uc0b0\ubd84\ud560",
        "query": (
            "\ubc30\uc6b0\uc790\uc640 \uc774\ud63c\ud558\uba74\uc11c "
            "\ud63c\uc778 \uc911 \ud568\uaed8 \ubaa8\uc740 "
            "\uc544\ud30c\ud2b8\uc640 \uc608\uae08\uc744 "
            "\uc7ac\uc0b0\ubd84\ud560\ud558\uace0 \uc2f6\uc2b5\ub2c8\ub2e4."
        ),
        "case_type": None,
        "case_subtype": None,
        "accepted_terms": [
            "\uc7ac\uc0b0\ubd84\ud560",
        ],
    },
    {
        "label": "\ubbf8\uc9c0\uae09 \uc591\uc721\ube44",
        "query": (
            "\uc774\ud63c\ud55c \uc804 \ubc30\uc6b0\uc790\uac00 "
            "\uc57d\uc18d\ud55c \uc591\uc721\ube44\ub97c "
            "\uacc4\uc18d \uc9c0\uae09\ud558\uc9c0 \uc54a\uace0 "
            "\uc788\uc2b5\ub2c8\ub2e4."
        ),
        "case_type": None,
        "case_subtype": None,
        "accepted_terms": [
            "\uc591\uc721\ube44",
        ],
    },
    {
        "label": "\uac1c\uba85 \uc2e0\uccad",
        "query": (
            "\ud604\uc7ac \uc774\ub984 \ub54c\ubb38\uc5d0 "
            "\uc0dd\ud65c\uc5d0 \ubd88\ud3b8\uc774 \ucee4\uc11c "
            "\ubc95\uc6d0\uc5d0 \uac1c\uba85\uc744 "
            "\uc2e0\uccad\ud558\uace0 \uc2f6\uc2b5\ub2c8\ub2e4."
        ),
        "case_type": "\uac00\uc871\uad00\uacc4\ub4f1\ub85d",
        "case_subtype": "\uc131\ubcf8\ucc3d\uc124\uacfc \uac1c\uba85",
        "accepted_terms": [
            "\uac1c\uba85\ud5c8\uac00\uc2e0\uccad\uc11c",
        ],
    },
    {
        "label": "\uc0c1\uc18d\ud3ec\uae30 \ud55c\uc815\uc2b9\uc778",
        "query": (
            "\ubd80\ubaa8\ub2d8\uc774 \ub0a8\uae34 "
            "\ube5a\uc774 \ub9ce\uc544\uc11c \uc0c1\uc18d\uc744 "
            "\ud3ec\uae30\ud558\uac70\ub098 \ud55c\uc815\uc2b9\uc778\uc744 "
            "\uc2e0\uccad\ud558\uace0 \uc2f6\uc2b5\ub2c8\ub2e4."
        ),
        "case_type": None,
        "case_subtype": None,
        "accepted_terms": [
            "\uc0c1\uc18d\ud55c\uc815\uc2b9\uc778",
            "\uc0c1\uc18d\ud3ec\uae30",
        ],
    },
    {
        "label": "\uc131\ub144\ud6c4\uacac",
        "query": (
            "\ubd80\ubaa8\ub2d8\uc774 \uce58\ub9e4\ub85c "
            "\uc7ac\uc0b0\uc744 \uad00\ub9ac\ud558\uae30 \uc5b4\ub824\uc6cc "
            "\uc131\ub144\ud6c4\uacac\uc778\uc744 "
            "\uc2e0\uccad\ud558\uace0 \uc2f6\uc2b5\ub2c8\ub2e4."
        ),
        "case_type": None,
        "case_subtype": None,
        "accepted_terms": [
            "\uc131\ub144\ud6c4\uacac",
            "\ud6c4\uacac\uac1c\uc2dc",
        ],
    },
    {
        "label": "\uac00\uc871\uad00\uacc4\ub4f1\ub85d\ubd80 \uc815\uc815",
        "query": (
            "\uac00\uc871\uad00\uacc4\ub4f1\ub85d\ubd80\uc5d0 "
            "\uc798\ubabb \uae30\uc7ac\ub41c \ub0b4\uc6a9\uc744 "
            "\ubc95\uc6d0\uc758 \ud5c8\uac00\ub97c \ubc1b\uc544 "
            "\uc815\uc815\ud558\uace0 \uc2f6\uc2b5\ub2c8\ub2e4."
        ),
        "case_type": None,
        "case_subtype": None,
        "accepted_terms": [
            "\ub4f1\ub85d\ubd80\uc815\uc815",
        ],
    },
    {
        "label": "\uce5c\uad8c\ud589\uc0ac\uc790 \uc9c0\uc815",
        "query": (
            "\uc774\ud63c \ud6c4 \uc544\uc774\ub97c "
            "\uc81c\uac00 \uc591\uc721\ud558\ub824\uace0 \ud558\uba70 "
            "\uce5c\uad8c\ud589\uc0ac\uc790\ub85c "
            "\uc9c0\uc815\ubc1b\uace0 \uc2f6\uc2b5\ub2c8\ub2e4."
        ),
        "case_type": "\uce5c\uc871",
        "case_subtype": "\uce5c\uad8c",
        "accepted_terms": [
            "\uce5c\uad8c\ud589\uc0ac\uc790",
            "\uce5c\uad8c\uc790\uc9c0\uc815",
        ],
    },
    {
        "label": "\uba74\uc811\uad50\uc12d",
        "query": (
            "\uc774\ud63c \ud6c4 \uc0c1\ub300\ubc29\uc774 "
            "\uc544\uc774\ub97c \ub9cc\ub098\uc9c0 \ubabb\ud558\uac8c "
            "\ud574\uc11c \uba74\uc811\uad50\uc12d\uc744 "
            "\uc2e0\uccad\ud558\uace0 \uc2f6\uc2b5\ub2c8\ub2e4."
        ),
        "case_type": "\uce5c\uc871",
        "case_subtype": "\uba74\uc811\uad50\uc12d\uad8c",
        "accepted_terms": [
            "\uba74\uc811\uad50\uc12d",
        ],
    },
    {
        "label": "\uc774\ud63c \uc704\uc790\ub8cc",
        "query": (
            "\ubc30\uc6b0\uc790\uc758 \ubd80\uc815\ud589\uc704 "
            "\ub54c\ubb38\uc5d0 \uc774\ud63c\ud558\uba74\uc11c "
            "\uc704\uc790\ub8cc\ub3c4 \ud568\uaed8 "
            "\uccad\uad6c\ud558\uace0 \uc2f6\uc2b5\ub2c8\ub2e4."
        ),
        "case_type": "\uce5c\uc871",
        "case_subtype": "\uc774\ud63c \ubc0f \uc704\uc790\ub8cc",
        "accepted_terms": [
            "\uc704\uc790\ub8cc",
        ],
    },
]


def _is_relevant(
    title: str,
    accepted_terms: list[str],
) -> bool:
    normalized_title = title.replace(" ", "")

    return any(
        term.replace(" ", "") in normalized_title
        for term in accepted_terms
    )


def _normalize_source(
    candidate: dict[str, Any],
) -> str:
    return str(
        candidate.get("source", "")
    ).strip().replace(
        "\\",
        "/",
    ).casefold()


def test_form_search_accuracy():
    top1_hits = 0
    top3_hits = 0
    failures: list[str] = []

    for case in SEARCH_CASES:
        candidates = search_rag_candidates(
            query_text=case["query"],
            top_n=3,
            case_type=case["case_type"],
            case_subtype=case["case_subtype"],
        )

        titles = [
            str(candidate.get("name", ""))
            for candidate in candidates
        ]

        sources = [
            source
            for source in (
                _normalize_source(candidate)
                for candidate in candidates
            )
            if source
        ]

        assert len(sources) == len(set(sources)), (
            f'{case["label"]}: 동일한 source가 '
            f"중복되었습니다: {sources}"
        )

        relevance = [
            _is_relevant(
                title,
                case["accepted_terms"],
            )
            for title in titles
        ]

        top1_hit = bool(
            relevance
            and relevance[0]
        )

        top3_hit = any(relevance)

        top1_hits += int(top1_hit)
        top3_hits += int(top3_hit)

        print()
        print("=" * 60)
        print("평가 항목:", case["label"])
        print("상담:", case["query"])
        print(
            "분류:",
            case["case_type"],
            ">",
            case["case_subtype"],
        )
        print(
            "정답 키워드:",
            ", ".join(
                case["accepted_terms"]
            ),
        )

        if not titles:
            print("검색 결과 없음")

        for rank, title in enumerate(
            titles,
            start=1,
        ):
            marker = (
                "정답"
                if relevance[rank - 1]
                else "오답"
            )

            print(
                f"{rank}. [{marker}] {title}"
            )

        print(
            "Top-1:",
            "성공" if top1_hit else "실패",
        )
        print(
            "Top-3:",
            "성공" if top3_hit else "실패",
        )

        if not top3_hit:
            failures.append(
                f'{case["label"]}: {titles}'
            )

    total = len(SEARCH_CASES)

    print()
    print("=" * 60)
    print(
        f"Top-1 정확도: "
        f"{top1_hits}/{total} "
        f"({top1_hits / total:.1%})"
    )
    print(
        f"Top-3 정확도: "
        f"{top3_hits}/{total} "
        f"({top3_hits / total:.1%})"
    )

    assert not failures, (
        "Top-3에서 관련 서식을 찾지 못한 항목:\n"
        + "\n".join(failures)
    )
