from app.ai.precedents.service import (
    find_related_precedents,
)


def test_precedent_service_uses_exact_anonymized_text():
    calls = {}
    anonymized_text = (
        "[PERSON]\uacfc \uc774\ud63c\ud558\uba70 "
        "\uc7ac\uc0b0\ubd84\ud560\uc744 \uccad\uad6c\ud569\ub2c8\ub2e4."
    )

    def fake_search(**kwargs):
        calls.update(kwargs)
        return [{"precedent_id": "100"}]

    results = find_related_precedents(
        anonymized_text=anonymized_text,
        top_n=3,
        search=fake_search,
    )

    assert calls == {
        "query_text": anonymized_text,
        "top_n": 3,
    }
    assert results == [
        {"precedent_id": "100"}
    ]


def test_precedent_service_does_not_search_without_anonymized_text():
    called = False

    def fake_search(**_kwargs):
        nonlocal called
        called = True
        return []

    results = find_related_precedents(
        anonymized_text="  ",
        search=fake_search,
    )

    assert results == []
    assert called is False
