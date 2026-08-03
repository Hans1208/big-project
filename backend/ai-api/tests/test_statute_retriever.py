from rag.statute_retriever import (
    StatuteRetriever,
    rerank_statute_candidates,
)


class FakeEmbeddingService:
    def __init__(self):
        self.queries = []

    def embed_query(self, text):
        self.queries.append(text)
        return [1.0, 0.0]


class FakeVectorStore:
    def __init__(self):
        self.calls = []

    def search(
        self,
        query_embedding,
        top_k,
        where=None,
    ):
        self.calls.append(
            {
                "query_embedding": query_embedding,
                "top_k": top_k,
                "where": where,
            }
        )

        return [
            {
                "id": (
                    "statute:001706:839:2"
                    "::chunk-0000"
                ),
                "document_id": (
                    "statute:001706:839:2"
                ),
                "title": (
                    "\ubbfc\ubc95 "
                    "\uc81c839\uc870\uc7582"
                    "(\uc7ac\uc0b0\ubd84\ud560"
                    "\uccad\uad6c\uad8c)"
                ),
                "content": (
                    "\uc7ac\uc0b0\ubd84\ud560\uc744 "
                    "\uccad\uad6c\ud560 \uc218 \uc788\ub2e4."
                ),
                "source": "law_api:001706",
                "similarity": 0.95,
                "law_id": "001706",
                "law_name": "\ubbfc\ubc95",
                "article_number": "839",
                "article_branch_number": "2",
                "article_label": (
                    "\uc81c839\uc870\uc7582"
                ),
                "article_title": (
                    "\uc7ac\uc0b0\ubd84\ud560"
                    "\uccad\uad6c\uad8c"
                ),
            },
            {
                "id": (
                    "statute:001706:839:2"
                    "::chunk-0001"
                ),
                "document_id": (
                    "statute:001706:839:2"
                ),
                "title": (
                    "\ubbfc\ubc95 "
                    "\uc81c839\uc870\uc7582"
                ),
                "content": (
                    "\uc7ac\uc0b0\ubd84\ud560 "
                    "\uccad\uad6c\uad8c\uc740 "
                    "2\ub144\uc774 \uc9c0\ub098\uba74 "
                    "\uc18c\uba78\ud55c\ub2e4."
                ),
                "source": "law_api:001706",
                "similarity": 0.94,
                "law_id": "001706",
                "law_name": "\ubbfc\ubc95",
                "article_number": "839",
                "article_branch_number": "2",
                "article_label": (
                    "\uc81c839\uc870\uc7582"
                ),
                "article_title": (
                    "\uc7ac\uc0b0\ubd84\ud560"
                    "\uccad\uad6c\uad8c"
                ),
            },
            {
                "id": (
                    "statute:001706:837:2"
                    "::chunk-0000"
                ),
                "document_id": (
                    "statute:001706:837:2"
                ),
                "title": (
                    "\ubbfc\ubc95 "
                    "\uc81c837\uc870\uc7582"
                    "(\uba74\uc811\uad50\uc12d\uad8c)"
                ),
                "content": (
                    "\ubd80\ubaa8\uc640 \uc790\ub294 "
                    "\uba74\uc811\uad50\uc12d\ud560 "
                    "\uc218 \uc788\ub2e4."
                ),
                "source": "law_api:001706",
                "similarity": 0.90,
                "law_id": "001706",
                "law_name": "\ubbfc\ubc95",
                "article_number": "837",
                "article_branch_number": "2",
                "article_label": (
                    "\uc81c837\uc870\uc7582"
                ),
                "article_title": (
                    "\uba74\uc811\uad50\uc12d\uad8c"
                ),
            },
        ]


def test_retrieve_returns_unique_articles_not_unique_sources():
    embedding_service = FakeEmbeddingService()
    vector_store = FakeVectorStore()

    retriever = StatuteRetriever(
        embedding_service=embedding_service,
        vector_store=vector_store,
    )

    results = retriever.retrieve(
        query=(
            "\uc774\ud63c\ud55c \ub4a4 "
            "\uc7ac\uc0b0\ubd84\ud560\uacfc "
            "\uba74\uc811\uad50\uc12d\uc5d0 "
            "\uad00\ud55c \ubc95\ub839"
        ),
        top_k=2,
    )

    assert embedding_service.queries == [
        (
            "\uc774\ud63c\ud55c \ub4a4 "
            "\uc7ac\uc0b0\ubd84\ud560\uacfc "
            "\uba74\uc811\uad50\uc12d\uc5d0 "
            "\uad00\ud55c \ubc95\ub839"
        )
    ]

    assert len(results) == 2

    assert results[0]["document_id"] == (
        "statute:001706:839:2"
    )
    assert results[0]["chunk_id"] == (
        "statute:001706:839:2::chunk-0000"
    )

    assert results[1]["document_id"] == (
        "statute:001706:837:2"
    )

    assert results[0]["source"] == (
        results[1]["source"]
    )


def test_retrieve_supports_law_id_filter():
    vector_store = FakeVectorStore()

    retriever = StatuteRetriever(
        embedding_service=FakeEmbeddingService(),
        vector_store=vector_store,
    )

    retriever.retrieve(
        query="\uc7ac\uc0b0\ubd84\ud560",
        law_id="001706",
        top_k=1,
    )

    assert vector_store.calls[0]["where"] == {
        "law_id": "001706",
    }


def test_retrieve_rejects_empty_query():
    retriever = StatuteRetriever(
        embedding_service=FakeEmbeddingService(),
        vector_store=FakeVectorStore(),
    )

    try:
        retriever.retrieve(
            query="   ",
        )
    except ValueError as error:
        assert "query" in str(error)
    else:
        raise AssertionError(
            "ValueError was not raised."
        )



def test_rerank_promotes_article_title_keyword_match():
    candidates = [
        {
            "document_id": "statute:001706:842:0",
            "similarity": 0.92,
            "law_name": "\ubbfc\ubc95",
            "article_label": "\uc81c842\uc870",
            "article_title": (
                "\uae30\ud0c0 \uc6d0\uc778\uc73c\ub85c "
                "\uc778\ud55c \uc774\ud63c\uccad\uad6c\uad8c\uc758 "
                "\uc18c\uba78"
            ),
        },
        {
            "document_id": "statute:001706:839:2",
            "similarity": 0.89,
            "law_name": "\ubbfc\ubc95",
            "article_label": "\uc81c839\uc870\uc7582",
            "article_title": (
                "\uc7ac\uc0b0\ubd84\ud560\uccad\uad6c\uad8c"
            ),
        },
    ]

    results = rerank_statute_candidates(
        query=(
            "\uc774\ud63c \ud6c4 "
            "\uc7ac\uc0b0\ubd84\ud560 \uccad\uad6c "
            "\uae30\uac04\uc740 \uc5bc\ub9c8\uc778\uac00\uc694?"
        ),
        candidates=candidates,
    )

    assert results[0]["document_id"] == (
        "statute:001706:839:2"
    )
    assert results[0]["similarity"] == 0.89
    assert results[0]["rerank_score"] > (
        results[1]["rerank_score"]
    )


def test_rerank_boosts_exact_article_label():
    candidates = [
        {
            "document_id": "statute:001706:839:2",
            "similarity": 0.82,
            "law_name": "\ubbfc\ubc95",
            "article_label": "\uc81c839\uc870\uc7582",
            "article_title": (
                "\uc7ac\uc0b0\ubd84\ud560\uccad\uad6c\uad8c"
            ),
        },
        {
            "document_id": "statute:001706:839:0",
            "similarity": 0.90,
            "law_name": "\ubbfc\ubc95",
            "article_label": "\uc81c839\uc870",
            "article_title": "\uc900\uc6a9\uaddc\uc815",
        },
    ]

    results = rerank_statute_candidates(
        query=(
            "\ubbfc\ubc95 \uc81c839\uc870\uc7582 "
            "\ub0b4\uc6a9\uc744 \uc54c\ub824\uc8fc\uc138\uc694."
        ),
        candidates=candidates,
    )

    assert results[0]["article_label"] == (
        "\uc81c839\uc870\uc7582"
    )
