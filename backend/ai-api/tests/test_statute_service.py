from types import SimpleNamespace

from app.ai.statutes.service import (
    build_statute_query,
    find_related_statutes,
)


def sample_analysis():
    return SimpleNamespace(
        summary=(
            "\ud611\uc758\uc774\ud63c \ud6c4 "
            "\uc7ac\uc0b0\ubd84\ud560\uc744 "
            "\uccad\uad6c\ud558\ub824\ub294 \uc0ac\uac74"
        ),
        case_type="\uac00\uc0ac\uc18c\uc1a1",
        case_subtype="\uc7ac\uc0b0\ubd84\ud560",
        extracted={
            "\uccad\uad6c\ub0b4\uc6a9": (
                "\uc7ac\uc0b0\ubd84\ud560"
            ),
            "\uc774\ud63c\uc77c": "2025-01-01",
        },
    )


def test_build_statute_query_uses_structured_analysis():
    query = build_statute_query(
        analysis=sample_analysis(),
        fallback_text=(
            "\uc0c1\ub2f4 \uc6d0\ubb38\uc740 "
            "\uad6c\uc870\ud654 \uacb0\uacfc\uac00 "
            "\uc788\uc73c\uba74 \uc81c\uc678\ub41c\ub2e4."
        ),
    )

    assert (
        "\uc0ac\uac74\uc694\uc57d: "
        "\ud611\uc758\uc774\ud63c \ud6c4 "
        "\uc7ac\uc0b0\ubd84\ud560"
        in query
    )
    assert (
        "\uc0ac\uac74\uc720\ud615: "
        "\uac00\uc0ac\uc18c\uc1a1"
        in query
    )
    assert (
        "\uc138\ubd80\uc720\ud615: "
        "\uc7ac\uc0b0\ubd84\ud560"
        in query
    )
    assert "\ucd94\ucd9c\uc815\ubcf4:" in query
    assert "\uccad\uad6c\ub0b4\uc6a9" in query
    assert "2025-01-01" in query
    assert "\uc0c1\ub2f4 \uc6d0\ubb38\uc740" not in query


def test_build_statute_query_falls_back_to_consult_text():
    analysis = SimpleNamespace(
        summary=None,
        case_type=None,
        case_subtype=None,
        extracted=None,
    )

    query = build_statute_query(
        analysis=analysis,
        fallback_text=(
            "\ubd80\ubaa8\ub2d8\uc774 "
            "\uc0ac\ub9dd\ud558\uc168\uace0 "
            "\uc0c1\uc18d \uc21c\uc704\uac00 "
            "\uad81\uae08\ud569\ub2c8\ub2e4."
        ),
    )

    assert query == (
        "\ubd80\ubaa8\ub2d8\uc774 "
        "\uc0ac\ub9dd\ud558\uc168\uace0 "
        "\uc0c1\uc18d \uc21c\uc704\uac00 "
        "\uad81\uae08\ud569\ub2c8\ub2e4."
    )


def test_find_related_statutes_calls_application_adapter():
    calls = {}

    def fake_search(**kwargs):
        calls.update(kwargs)

        return [
            {
                "citation": (
                    "\ubbfc\ubc95 "
                    "\uc81c839\uc870\uc7582"
                ),
            }
        ]

    results = find_related_statutes(
        analysis=sample_analysis(),
        fallback_text="\uc0c1\ub2f4 \uc6d0\ubb38",
        top_n=3,
        search=fake_search,
    )

    assert calls["top_n"] == 3
    assert (
        "\uc7ac\uc0b0\ubd84\ud560"
        in calls["query_text"]
    )
    assert results == [
        {
            "citation": (
                "\ubbfc\ubc95 "
                "\uc81c839\uc870\uc7582"
            ),
        }
    ]
