from __future__ import annotations

import pytest

from app.ai.consultations.service import (
    find_related_consultations,
)


def test_service_uses_only_cleaned_anonymized_text():
    calls = {}

    def fake_search(**kwargs):
        calls.update(kwargs)

        return [
            {
                "consultation_id": (
                    "consultation-1"
                )
            }
        ]

    results = find_related_consultations(
        anonymized_text=(
            "  [PERSON]\uacfc \uc774\ud63c\ud558\uba70  \n"
            "\n"
            "  \uc591\uc721\ube44\ub97c "
            "\uccad\uad6c\ud569\ub2c8\ub2e4.  "
        ),
        top_n=3,
        search=fake_search,
    )

    assert calls == {
        "query_text": (
            "[PERSON]\uacfc \uc774\ud63c\ud558\uba70\n"
            "\uc591\uc721\ube44\ub97c "
            "\uccad\uad6c\ud569\ub2c8\ub2e4."
        ),
        "top_n": 3,
    }

    assert results == [
        {
            "consultation_id": (
                "consultation-1"
            )
        }
    ]


def test_service_does_not_search_blank_text():
    called = False

    def fake_search(**_kwargs):
        nonlocal called
        called = True
        return []

    results = find_related_consultations(
        anonymized_text=" \n ",
        search=fake_search,
    )

    assert results == []
    assert called is False


def test_service_fails_open():
    def broken_search(**_kwargs):
        raise RuntimeError("broken")

    assert find_related_consultations(
        anonymized_text="\uc591\uc721\ube44 \ubb38\uc758",
        search=broken_search,
    ) == []


def test_service_rejects_invalid_top_n():
    with pytest.raises(
        ValueError,
        match="top_n",
    ):
        find_related_consultations(
            anonymized_text="\uc0c1\uc18d \ubb38\uc758",
            top_n=0,
        )
