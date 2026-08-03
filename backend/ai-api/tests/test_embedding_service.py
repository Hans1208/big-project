import numpy as np

from rag.embedding_service import EmbeddingService


class FakeModel:
    def __init__(self):
        self.calls = []

    def encode(self, sentences, **kwargs):
        self.calls.append(
            {
                "sentences": sentences,
                "kwargs": kwargs,
            }
        )

        if sentences[0].startswith("query: "):
            return np.array(
                [[0.6, 0.8]],
                dtype=np.float32,
            )

        return np.array(
            [
                [1.0, 0.0],
                [0.0, 1.0],
            ],
            dtype=np.float32,
        )


def test_embed_documents_adds_passage_prefix():
    fake_model = FakeModel()
    service = EmbeddingService(model=fake_model)

    vectors = service.embed_documents(
        [
            "이혼 및 재산분할 청구서",
            "개명허가 신청서",
        ]
    )

    assert fake_model.calls[0]["sentences"] == [
        "passage: 이혼 및 재산분할 청구서",
        "passage: 개명허가 신청서",
    ]
    assert (
        fake_model.calls[0]["kwargs"]["normalize_embeddings"]
        is True
    )
    assert vectors == [
        [1.0, 0.0],
        [0.0, 1.0],
    ]


def test_embed_query_adds_query_prefix():
    fake_model = FakeModel()
    service = EmbeddingService(model=fake_model)

    vector = service.embed_query(
        "배우자와 이혼하면서 재산을 나누고 싶습니다."
    )

    assert fake_model.calls[0]["sentences"] == [
        "query: 배우자와 이혼하면서 재산을 나누고 싶습니다."
    ]
    assert (
        fake_model.calls[0]["kwargs"]["normalize_embeddings"]
        is True
    )
    assert vector == [0.6000000238418579, 0.800000011920929]
