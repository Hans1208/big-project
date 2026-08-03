from rag.build_statute_index import (
    build_statute_index,
)


class FakeLawApiClient:
    def __init__(self):
        self.search_calls = []
        self.detail_calls = []

    def search_current_laws(
        self,
        query,
        display=20,
        page=1,
    ):
        self.search_calls.append(
            {
                "query": query,
                "display": display,
                "page": page,
            }
        )

        return [
            {
                "law_id": "011546",
                "mst": "188376",
                "name": "\ub09c\ubbfc\ubc95",
            },
            {
                "law_id": "001706",
                "mst": "284415",
                "name": "\ubbfc\ubc95",
            },
        ]

    def get_current_law(self, law_id):
        self.detail_calls.append(law_id)

        return {
            "\ubc95\ub839": {
                "\ubc95\ub839\ud0a4": (
                    "0017062026031721454"
                ),
                "\uae30\ubcf8\uc815\ubcf4": {
                    "\ubc95\ub839ID": "001706",
                    "\ubc95\ub839\uba85_\ud55c\uae00": (
                        "\ubbfc\ubc95"
                    ),
                    "\uc2dc\ud589\uc77c\uc790": (
                        "20260317"
                    ),
                    "\ubc95\uc885\uad6c\ubd84": {
                        "content": "\ubc95\ub960",
                    },
                    "\uc18c\uad00\ubd80\ucc98": {
                        "content": "\ubc95\ubb34\ubd80",
                    },
                },
                "\uc870\ubb38": {
                    "\uc870\ubb38\ub2e8\uc704": [
                        {
                            "\uc870\ubb38\ud0a4": "10001",
                            "\uc870\ubb38\ubc88\ud638": "1",
                            "\uc870\ubb38\uc5ec\ubd80": (
                                "\uc870\ubb38"
                            ),
                            "\uc870\ubb38\uc81c\ubaa9": (
                                "\ubc95\uc6d0"
                            ),
                            "\uc870\ubb38\ub0b4\uc6a9": (
                                "\uc81c1\uc870"
                                "(\ubc95\uc6d0)"
                            ),
                        }
                    ]
                },
            }
        }


class FakeEmbeddingService:
    def __init__(self):
        self.batches = []

    def embed_documents(self, texts):
        self.batches.append(list(texts))

        return [
            [1.0, 0.0]
            for _ in texts
        ]


class FakeVectorStore:
    def __init__(self):
        self.documents = []

    def upsert_documents(
        self,
        documents,
        embeddings,
    ):
        assert len(documents) == len(embeddings)
        self.documents.extend(documents)

    def count(self):
        return len(self.documents)


def test_build_statute_index_uses_exact_law_name():
    api_client = FakeLawApiClient()
    embedding_service = FakeEmbeddingService()
    vector_store = FakeVectorStore()

    result = build_statute_index(
        law_names=("\ubbfc\ubc95",),
        batch_size=2,
        api_client=api_client,
        embedding_service=embedding_service,
        vector_store=vector_store,
    )

    assert api_client.search_calls == [
        {
            "query": "\ubbfc\ubc95",
            "display": 100,
            "page": 1,
        }
    ]

    assert api_client.detail_calls == [
        "001706"
    ]

    assert result == {
        "laws": 1,
        "articles": 1,
        "chunks": 1,
        "stored": 1,
    }

    assert len(vector_store.documents) == 1

    stored = vector_store.documents[0]

    assert stored["law_name"] == "\ubbfc\ubc95"
    assert stored["document_type"] == (
        "legal_statute"
    )
    assert stored["article_number"] == "1"

    assert len(embedding_service.batches) == 1
    assert "\ubc95\ub839\uba85: \ubbfc\ubc95" in (
        embedding_service.batches[0][0]
    )
