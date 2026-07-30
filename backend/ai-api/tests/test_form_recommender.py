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
