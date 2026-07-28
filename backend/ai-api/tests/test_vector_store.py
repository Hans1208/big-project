import pytest

from rag.vector_store import ChromaVectorStore


def sample_documents():
    return [
        {
            "document_id": "FORM-001",
            "document_type": "legal_form",
            "title": "이혼 및 재산분할청구의 소",
            "case_type": "가사소송",
            "case_subtype": "가,나,다류 가사소송",
            "content": (
                "배우자와 이혼하면서 공동으로 형성한 "
                "재산의 분할을 청구하는 서식"
            ),
            "source": "forms/divorce-property.hwpx",
        },
        {
            "document_id": "FORM-002",
            "document_type": "legal_form",
            "title": "개명허가신청서",
            "case_type": "가족관계등록",
            "case_subtype": "성본창설과 개명",
            "content": (
                "현재 이름을 새로운 이름으로 변경하기 위해 "
                "법원에 허가를 구하는 서식"
            ),
            "source": "forms/name-change.hwpx",
        },
    ]


def test_upsert_documents_stores_documents_and_metadata(tmp_path):
    store = ChromaVectorStore(
        persist_directory=tmp_path / "chroma",
        collection_name="test-legal-forms",
    )

    documents = sample_documents()
    embeddings = [
        [1.0, 0.0],
        [0.0, 1.0],
    ]

    store.upsert_documents(
        documents=documents,
        embeddings=embeddings,
    )

    assert store.count() == 2

    stored = store.collection.get(
        ids=["FORM-001"],
        include=["documents", "metadatas"],
    )

    assert stored["documents"] == [
        documents[0]["content"]
    ]
    assert stored["metadatas"][0]["title"] == (
        "이혼 및 재산분할청구의 소"
    )
    assert stored["metadatas"][0]["case_type"] == (
        "가사소송"
    )


def test_search_returns_most_similar_document_first(tmp_path):
    store = ChromaVectorStore(
        persist_directory=tmp_path / "chroma",
        collection_name="test-legal-forms",
    )

    store.upsert_documents(
        documents=sample_documents(),
        embeddings=[
            [1.0, 0.0],
            [0.0, 1.0],
        ],
    )

    results = store.search(
        query_embedding=[1.0, 0.0],
        top_k=2,
    )

    assert len(results) == 2
    assert results[0]["id"] == "FORM-001"
    assert results[0]["title"] == (
        "이혼 및 재산분할청구의 소"
    )
    assert results[0]["similarity"] == pytest.approx(
        1.0,
        abs=0.001,
    )
    assert results[1]["id"] == "FORM-002"


def test_search_supports_metadata_filter(tmp_path):
    store = ChromaVectorStore(
        persist_directory=tmp_path / "chroma",
        collection_name="test-legal-forms",
    )

    store.upsert_documents(
        documents=sample_documents(),
        embeddings=[
            [1.0, 0.0],
            [0.0, 1.0],
        ],
    )

    results = store.search(
        query_embedding=[0.0, 1.0],
        top_k=2,
        where={
            "case_type": "가사소송",
        },
    )

    assert len(results) == 1
    assert results[0]["id"] == "FORM-001"


def test_upsert_rejects_different_document_and_embedding_counts(
    tmp_path,
):
    store = ChromaVectorStore(
        persist_directory=tmp_path / "chroma",
        collection_name="test-legal-forms",
    )

    with pytest.raises(
        ValueError,
        match="문서 수와 임베딩 수",
    ):
        store.upsert_documents(
            documents=sample_documents(),
            embeddings=[[1.0, 0.0]],
        )


class CapturingClient:
    def __init__(self):
        self.configuration = None

    def get_or_create_collection(self, **kwargs):
        self.configuration = kwargs["configuration"]
        return object()


def test_collection_uses_frequent_hnsw_sync(tmp_path):
    client = CapturingClient()

    ChromaVectorStore(
        persist_directory=tmp_path / "chroma",
        collection_name="test-sync-settings",
        client=client,
    )

    hnsw_config = client.configuration["hnsw"]

    assert hnsw_config["space"] == "cosine"
    assert hnsw_config["batch_size"] == 100
    assert hnsw_config["sync_threshold"] == 100
