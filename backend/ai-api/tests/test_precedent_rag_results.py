from app.ai.precedents.rag_results import (
    convert_rag_results_to_precedents,
    search_precedent_rag,
)


def _result(
    precedent_id="100",
    chunk_id="precedent:100:holding::chunk-0000",
):
    return {
        "id": chunk_id,
        "document_id": (
            f"precedent:{precedent_id}:holding"
        ),
        "precedent_id": precedent_id,
        "case_name": "\uc7ac\uc0b0\ubd84\ud560",
        "case_number": "2024\ub290\ud569100",
        "decision_date": "20250101",
        "court_name": "\uc11c\uc6b8\uac00\uc815\ubc95\uc6d0",
        "court_level": "LOWER",
        "case_type_name": "\uac00\uc0ac",
        "decision_type": "\ud310\uacb0",
        "section_type": "holding",
        "section_label": "\ud310\uc2dc\uc0ac\ud56d",
        "holding": "\uc7ac\uc0b0\ubd84\ud560 \uae30\uc900",
        "summary": "\ud63c\uc778 \uc911 \ud615\uc131\ud55c \uc7ac\uc0b0",
        "content": "\uc7ac\uc0b0\ubd84\ud560 \ub300\uc0c1\uc744 \ud310\ub2e8\ud55c\ub2e4.",
        "referenced_statutes": "\ubbfc\ubc95 \uc81c839\uc870\uc7582",
        "referenced_precedents": "",
        "similarity": 0.82,
        "rerank_score": 1.02,
        "source": "law_api:prec:100",
    }


def test_convert_precedent_result():
    results = convert_rag_results_to_precedents(
        [_result()]
    )

    assert len(results) == 1

    converted = results[0]

    assert converted["precedent_id"] == "100"
    assert converted["case_name"] == "\uc7ac\uc0b0\ubd84\ud560"
    assert converted["court_level"] == "LOWER"
    assert converted["section_type"] == "holding"
    assert converted["chunk_id"].endswith(
        "chunk-0000"
    )
    assert converted["similarity"] == 0.82
    assert converted["rerank_score"] == 1.02


def test_convert_precedent_results_deduplicates_cases():
    results = convert_rag_results_to_precedents(
        [
            _result(
                chunk_id=(
                    "precedent:100:holding::chunk-0000"
                )
            ),
            _result(
                chunk_id=(
                    "precedent:100:full_text::chunk-0001"
                )
            ),
        ]
    )

    assert len(results) == 1
    assert results[0]["precedent_id"] == "100"


def test_search_precedent_rag_calls_retriever():
    calls = {}

    def fake_retrieve(**kwargs):
        calls.update(kwargs)
        return [_result()]

    results = search_precedent_rag(
        query_text="\uc774\ud63c \uc7ac\uc0b0\ubd84\ud560",
        top_n=2,
        court_level="LOWER",
        retrieve=fake_retrieve,
    )

    assert calls == {
        "query": "\uc774\ud63c \uc7ac\uc0b0\ubd84\ud560",
        "top_k": 2,
        "court_level": "LOWER",
    }
    assert len(results) == 1


def test_search_precedent_rag_fails_open():
    def broken_retrieve(**_kwargs):
        raise RuntimeError("broken")

    assert search_precedent_rag(
        query_text="\uc774\ud63c",
        retrieve=broken_retrieve,
    ) == []
