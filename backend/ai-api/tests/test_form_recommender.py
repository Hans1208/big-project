import importlib
import sys

import openai


def test_recommender_import_does_not_create_openai_client(
    monkeypatch,
):
    def fail_if_created(*args, **kwargs):
        raise AssertionError(
            "OpenAI client was created during import."
        )

    monkeypatch.setattr(
        openai,
        "OpenAI",
        fail_if_created,
    )

    sys.modules.pop(
        "app.ai.forms.recommender",
        None,
    )

    module = importlib.import_module(
        "app.ai.forms.recommender"
    )

    assert callable(module.get_candidates)


def test_get_candidates_forwards_classification_to_rag(
    monkeypatch,
):
    from app.ai.forms import recommender

    captured = {}

    def fake_search(
        query_text,
        top_n=10,
        **kwargs,
    ):
        captured["query_text"] = query_text
        captured["top_n"] = top_n
        captured.update(kwargs)

        return []

    monkeypatch.setattr(
        recommender,
        "_load_mapping",
        lambda: [],
    )

    monkeypatch.setattr(
        recommender,
        "search_rag_candidates",
        fake_search,
    )

    candidates = recommender.get_candidates(
        "가족관계등록",
        "성본창설과 개명",
        (
            "현재 이름 때문에 생활에 불편이 커서 "
            "개명을 신청하고 싶습니다."
        ),
    )

    assert candidates == []

    assert captured == {
        "query_text": (
            "현재 이름 때문에 생활에 불편이 커서 "
            "개명을 신청하고 싶습니다."
        ),
        "top_n": recommender.EMBEDDING_TOP_N,
        "case_type": "가족관계등록",
        "case_subtype": "성본창설과 개명",
    }
