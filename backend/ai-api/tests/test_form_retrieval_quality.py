import pytest

from app.ai.forms.rag_candidates import (
    search_rag_candidates,
)


def _search_names(
    query: str,
    top_n: int = 3,
    case_type: str | None = None,
    case_subtype: str | None = None,
) -> list[str]:
    results = search_rag_candidates(
        query_text=query,
        top_n=top_n,
        case_type=case_type,
        case_subtype=case_subtype,
    )

    names = [
        result["name"]
        for result in results
    ]

    print()
    print("상담:", query)
    print("분류:", case_type, ">", case_subtype)

    for rank, name in enumerate(
        names,
        start=1,
    ):
        print(f"{rank}. {name}")

    return names


def _contains_any(
    text: str,
    keywords: tuple[str, ...],
) -> bool:
    return any(
        keyword in text
        for keyword in keywords
    )


def test_divorce_property_division_top_result_is_relevant():
    names = _search_names(
        "배우자와 이혼하면서 혼인 중 함께 모은 "
        "아파트와 예금을 재산분할하고 싶습니다."
    )

    assert names

    assert _contains_any(
        names[0],
        (
            "이혼",
            "재산분할",
        ),
    ), (
        "이혼·재산분할 상담인데 첫 번째 결과가 "
        f"관련 서식이 아닙니다: {names}"
    )


def test_classified_name_change_returns_name_change_form():
    names = _search_names(
        query=(
            "현재 이름 때문에 생활에 불편이 커서 "
            "법원에 개명을 신청하고 싶습니다."
        ),
        case_type="가족관계등록",
        case_subtype="성본창설과 개명",
    )

    assert names

    assert any(
        "개명" in name
        for name in names
    ), (
        "개명 분류를 전달했지만 개명 서식이 "
        f"상위 3개에 없습니다: {names}"
    )


@pytest.mark.parametrize(
    ("query", "expected_keywords"),
    [
        (
            "이혼한 전 배우자가 약속한 양육비를 "
            "계속 지급하지 않고 있습니다.",
            (
                "양육비",
                "이행명령",
            ),
        ),
        (
            "부모님이 남긴 빚이 많아서 상속을 "
            "포기하거나 한정승인을 신청하고 싶습니다.",
            (
                "상속포기",
                "한정승인",
            ),
        ),
    ],
)
def test_expected_form_appears_in_top_3(
    query: str,
    expected_keywords: tuple[str, ...],
):
    names = _search_names(query)

    assert names

    assert any(
        _contains_any(
            name,
            expected_keywords,
        )
        for name in names
    ), (
        f"기대 키워드 {expected_keywords}가 "
        f"상위 3개에 없습니다: {names}"
    )
