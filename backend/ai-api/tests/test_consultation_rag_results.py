from __future__ import annotations

from app.ai.consultations.rag_results import (
    build_consultation_context,
    convert_rag_results_to_consultations,
    search_consultation_rag,
)


def _result(
    consultation_id=(
        "consultation-"
        "0123456789abcdef01234567"
    ),
    *,
    source_type="case",
    answer=None,
):
    if answer is None:
        answer = (
            "\uc0c1\uc18d\uac1c\uc2dc\ub97c "
            "\uc548 \ub0a0\ubd80\ud130 "
            "3\uac1c\uc6d4 \uc548\uc5d0 "
            "\uc0c1\uc18d\ud3ec\uae30\ub97c "
            "\uc2e0\uace0\ud560 \uc218 "
            "\uc788\uc2b5\ub2c8\ub2e4."
        )

    return {
        "id": (
            f"consultation:"
            f"{consultation_id}"
            "::chunk-0000"
        ),
        "consultation_id": (
            consultation_id
        ),
        "source_type": source_type,
        "service_category": (
            "inheritance"
        ),
        "legal_path": (
            "\uc0c1\uc18d\uacfc\uc720\uc5b8>"
            "\uc0c1\uc18d\ud3ec\uae30"
        ),
        "question": (
            "\ubd80\ubaa8\ub2d8\uc774 "
            "\ube5a\uc744 \ub0a8\uae30\uace0 "
            "\uc0ac\ub9dd\ud588\uc2b5\ub2c8\ub2e4."
        ),
        "answer": answer,
        "content": answer,
        "source_date": "2024-07-31",
        "similarity": 0.91,
        "rerank_score": 1.20,
    }


def test_convert_consultation_result():
    converted = (
        convert_rag_results_to_consultations(
            [_result()]
        )
    )

    assert len(converted) == 1

    result = converted[0]

    assert result["consultation_id"] == (
        "consultation-"
        "0123456789abcdef01234567"
    )
    assert result["source_type"] == "case"
    assert result["service_category"] == (
        "inheritance"
    )
    assert result["legal_path"] == (
        "\uc0c1\uc18d\uacfc\uc720\uc5b8>"
        "\uc0c1\uc18d\ud3ec\uae30"
    )
    assert result["question"]
    assert result["answer_excerpt"]
    assert result["source_date"] == (
        "2024-07-31"
    )
    assert result["similarity"] == 0.91
    assert result["rerank_score"] == 1.20


def test_answer_excerpt_is_limited():
    converted = (
        convert_rag_results_to_consultations(
            [
                _result(
                    answer="A" * 700
                )
            ],
        )
    )

    excerpt = converted[0][
        "answer_excerpt"
    ]

    assert len(excerpt) == 600
    assert excerpt.endswith("\u2026")


def test_conversion_deduplicates_consultations():
    result = _result()

    duplicate = dict(result)
    duplicate["id"] = (
        "duplicate::chunk-0001"
    )

    converted = (
        convert_rag_results_to_consultations(
            [
                result,
                duplicate,
            ]
        )
    )

    assert len(converted) == 1


def test_conversion_drops_invalid_results():
    missing_id = _result()
    missing_id["consultation_id"] = ""

    missing_question = _result(
        consultation_id="missing-question"
    )
    missing_question["question"] = ""

    missing_answer = _result(
        consultation_id="missing-answer"
    )
    missing_answer["answer"] = ""
    missing_answer["content"] = ""

    assert (
        convert_rag_results_to_consultations(
            [
                missing_id,
                missing_question,
                missing_answer,
            ]
        )
        == []
    )


def test_search_consultation_rag_calls_retriever():
    calls = {}

    def fake_retrieve(**kwargs):
        calls.update(kwargs)
        return [_result()]

    results = search_consultation_rag(
        query_text=(
            "\uc0c1\uc18d\uc744 "
            "\ud3ec\uae30\ud558\uace0 "
            "\uc2f6\uc2b5\ub2c8\ub2e4."
        ),
        top_n=3,
        retrieve=fake_retrieve,
    )

    assert calls == {
        "query": (
            "\uc0c1\uc18d\uc744 "
            "\ud3ec\uae30\ud558\uace0 "
            "\uc2f6\uc2b5\ub2c8\ub2e4."
        ),
        "top_k": 3,
    }

    assert len(results) == 1


def test_search_consultation_rag_fails_open():
    def broken_retrieve(**_kwargs):
        raise RuntimeError("broken")

    results = search_consultation_rag(
        query_text="\uc0c1\uc18d\ud3ec\uae30",
        retrieve=broken_retrieve,
    )

    assert results == []


def test_build_context_marks_consultations_as_reference_only():
    consultations = (
        convert_rag_results_to_consultations(
            [_result()]
        )
    )

    context = (
        build_consultation_context(
            consultations
        )
    )

    assert context.startswith(
        "[\uc720\uc0ac \uc0c1\ub2f4\uc0ac\ub840 "
        "\u2014 \ubc95\uc801 \uadfc\uac70\uac00 "
        "\uc544\ub2cc \ucc38\uace0\uc790\ub8cc]"
    )

    assert (
        "\uc9c8\ubb38:"
        in context
    )
    assert (
        "\ub2f5\ubcc0:"
        in context
    )
    assert (
        "2024-07-31"
        in context
    )


def test_build_context_respects_max_characters():
    consultations = (
        convert_rag_results_to_consultations(
            [
                _result(
                    answer="A" * 700
                )
            ]
        )
    )

    context = build_consultation_context(
        consultations,
        max_characters=150,
    )

    assert len(context) <= 150
