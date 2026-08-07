from app.routers import precedents
from app.routers import statutes


def test_statute_search_caps_top_k_at_100(
    monkeypatch,
):
    captured = {}

    def fake_retrieve_statutes(
        *,
        query,
        law_id,
        top_k,
    ):
        captured["top_k"] = top_k
        return []

    monkeypatch.setattr(
        statutes,
        "retrieve_statutes",
        fake_retrieve_statutes,
    )

    result = statutes._search(
        query="inheritance",
        law_id=None,
        top_k=9999,
    )

    assert statutes.MAX_TOP_K == 100
    assert captured["top_k"] == 100
    assert result == []


def test_precedent_search_caps_top_k_at_100(
    monkeypatch,
):
    captured = {}

    def fake_search_precedent_rag(
        *,
        query_text,
        top_n,
        court_level,
    ):
        captured["top_n"] = top_n
        return []

    monkeypatch.setattr(
        precedents,
        "search_precedent_rag",
        fake_search_precedent_rag,
    )

    result = precedents._search(
        query="inheritance",
        court_level=None,
        top_k=9999,
    )

    assert precedents.MAX_TOP_K == 100
    assert captured["top_n"] == (
        100
        * precedents.CHUNK_OVERFETCH
    )
    assert result == []
