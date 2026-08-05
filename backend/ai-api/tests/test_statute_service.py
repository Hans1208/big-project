from app.ai.statutes.service import (
    build_statute_query,
    find_related_statutes,
)


def test_build_statute_query_uses_only_anonymized_text():
    anonymized_text = (
        "[PERSON]\uacfc \uc774\ud63c\ud55c \ud6c4 "
        "\uc7ac\uc0b0\ubd84\ud560\uc744 \uccad\uad6c\ud569\ub2c8\ub2e4."
    )

    assert build_statute_query(
        anonymized_text
    ) == anonymized_text


def test_statute_service_passes_exact_anonymized_text():
    calls = {}
    anonymized_text = (
        "[PERSON]\uc758 \uc0c1\uc18d\uc7ac\uc0b0\uc744 "
        "\ubd84\ud560\ud558\uace0 \uc2f6\uc2b5\ub2c8\ub2e4."
    )

    def fake_search(**kwargs):
        calls.update(kwargs)
        return [{"citation": "\ubbfc\ubc95 \uc81c1000\uc870"}]

    results = find_related_statutes(
        anonymized_text=anonymized_text,
        top_n=4,
        search=fake_search,
    )

    assert calls == {
        "query_text": anonymized_text,
        "top_n": 4,
    }
    assert results == [
        {"citation": "\ubbfc\ubc95 \uc81c1000\uc870"}
    ]


def test_statute_service_does_not_fallback_to_raw_text():
    called = False

    def fake_search(**_kwargs):
        nonlocal called
        called = True
        return []

    results = find_related_statutes(
        anonymized_text="",
        search=fake_search,
    )

    assert results == []
    assert called is False


def test_statute_service_fails_open():
    def broken_search(**_kwargs):
        raise RuntimeError("broken")

    assert find_related_statutes(
        anonymized_text="\uc774\ud63c",
        search=broken_search,
    ) == []
