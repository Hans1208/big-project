from app.ai.statutes.rag_results import (
    build_statute_context,
    convert_rag_result_to_statute,
    convert_rag_results_to_statutes,
    search_statute_rag,
)


def sample_result():
    return {
        "document_id": "statute:001706:839:2",
        "chunk_id": (
            "statute:001706:839:2::chunk-0000"
        ),
        "law_id": "001706",
        "law_name": "\ubbfc\ubc95",
        "article_number": "839",
        "article_branch_number": "2",
        "article_label": "\uc81c839\uc870\uc7582",
        "article_title": (
            "\uc7ac\uc0b0\ubd84\ud560\uccad\uad6c\uad8c"
        ),
        "effective_date": "20260317",
        "content": (
            "\ud611\uc758\uc0c1 \uc774\ud63c\ud55c "
            "\uc790\uc758 \uc77c\ubc29\uc740 "
            "\ub2e4\ub978 \uc77c\ubc29\uc5d0 "
            "\ub300\ud558\uc5ec "
            "\uc7ac\uc0b0\ubd84\ud560\uc744 "
            "\uccad\uad6c\ud560 \uc218 \uc788\ub2e4."
        ),
        "similarity": 0.9015,
        "rerank_score": 0.9815,
        "source": "law_api:001706",
    }


def test_convert_rag_result_to_statute():
    converted = convert_rag_result_to_statute(
        sample_result()
    )

    assert converted == {
        "document_id": "statute:001706:839:2",
        "chunk_id": (
            "statute:001706:839:2::chunk-0000"
        ),
        "law_id": "001706",
        "law_name": "\ubbfc\ubc95",
        "article_number": "839",
        "article_branch_number": "2",
        "article_label": "\uc81c839\uc870\uc7582",
        "article_title": (
            "\uc7ac\uc0b0\ubd84\ud560\uccad\uad6c\uad8c"
        ),
        "citation": (
            "\ubbfc\ubc95 "
            "\uc81c839\uc870\uc7582"
            "(\uc7ac\uc0b0\ubd84\ud560\uccad\uad6c\uad8c)"
        ),
        "effective_date": "20260317",
        "content": sample_result()["content"],
        "similarity": 0.9015,
        "rerank_score": 0.9815,
        "source": "law_api:001706",
    }


def test_search_statute_rag_calls_local_retriever():
    calls = {}

    def fake_retrieve(**kwargs):
        calls.update(kwargs)
        return [sample_result()]

    results = search_statute_rag(
        query_text=(
            "\uc774\ud63c \ud6c4 "
            "\uc7ac\uc0b0\ubd84\ud560 \uae30\uac04"
        ),
        top_n=3,
        law_id="001706",
        retrieve=fake_retrieve,
    )

    assert calls == {
        "query": (
            "\uc774\ud63c \ud6c4 "
            "\uc7ac\uc0b0\ubd84\ud560 \uae30\uac04"
        ),
        "top_k": 3,
        "law_id": "001706",
    }

    assert len(results) == 1
    assert results[0]["citation"] == (
        "\ubbfc\ubc95 "
        "\uc81c839\uc870\uc7582"
        "(\uc7ac\uc0b0\ubd84\ud560\uccad\uad6c\uad8c)"
    )


def test_convert_results_removes_invalid_and_duplicate_rows():
    duplicate = {
        **sample_result(),
        "chunk_id": (
            "statute:001706:839:2::chunk-0001"
        ),
    }

    invalid = {
        **sample_result(),
        "document_id": "",
    }

    results = convert_rag_results_to_statutes(
        [
            sample_result(),
            duplicate,
            invalid,
        ]
    )

    assert len(results) == 1
    assert results[0]["document_id"] == (
        "statute:001706:839:2"
    )


def test_search_statute_rag_returns_empty_on_failure():
    def failing_retrieve(**kwargs):
        raise RuntimeError(
            "vector store unavailable"
        )

    results = search_statute_rag(
        query_text="\uc7ac\uc0b0\ubd84\ud560",
        retrieve=failing_retrieve,
    )

    assert results == []


def test_build_statute_context_formats_sources():
    context = build_statute_context(
        [convert_rag_result_to_statute(
            sample_result()
        )]
    )

    assert (
        "[1] \ubbfc\ubc95 "
        "\uc81c839\uc870\uc7582"
        "(\uc7ac\uc0b0\ubd84\ud560\uccad\uad6c\uad8c)"
        in context
    )
    assert "\uc2dc\ud589\uc77c: 20260317" in context
    assert sample_result()["content"] in context
