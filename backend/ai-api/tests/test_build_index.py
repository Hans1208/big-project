import json

from rag.build_index import build_form_index


class FakeEmbeddingService:
    def __init__(self):
        self.calls = []

    def embed_documents(self, texts):
        self.calls.append(list(texts))

        return [
            [1.0, 0.0]
            for _ in texts
        ]


class FakeVectorStore:
    def __init__(self):
        self.batches = []

    def upsert_documents(
        self,
        documents,
        embeddings,
    ):
        self.batches.append(
            {
                "documents": list(documents),
                "embeddings": list(embeddings),
            }
        )

    def count(self):
        return sum(
            len(batch["documents"])
            for batch in self.batches
        )


def test_build_form_index_loads_chunks_and_stores_batches(
    tmp_path,
):
    parsed_file = tmp_path / "forms.json"

    parsed_file.write_text(
        json.dumps(
            [
                {
                    "form_name": "이혼청구의 소",
                    "main": "가사소송",
                    "sub": "가,나,다류 가사소송",
                    "tmpltNo": "FORM-001",
                    "source_file": "forms/divorce.hwpx",
                    "markdown": (
                        "배우자와 재판상 이혼을 청구하는 서식"
                    ),
                },
                {
                    "form_name": "개명허가신청서",
                    "main": "가족관계등록",
                    "sub": "성본창설과 개명",
                    "tmpltNo": "FORM-002",
                    "source_file": "forms/name-change.hwpx",
                    "markdown": (
                        "현재 이름을 변경하기 위한 신청서"
                    ),
                },
            ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    embedding_service = FakeEmbeddingService()
    vector_store = FakeVectorStore()

    result = build_form_index(
        parsed_file=parsed_file,
        embedding_service=embedding_service,
        vector_store=vector_store,
        chunk_size=1000,
        chunk_overlap=100,
        batch_size=1,
    )

    assert result == {
        "documents": 2,
        "chunks": 2,
        "stored": 2,
    }

    assert len(
        embedding_service.calls
    ) == 2

    assert len(
        vector_store.batches
    ) == 2

    first_embedding_text = (
        embedding_service.calls[0][0]
    )

    assert "서식명: 이혼청구의 소" in (
        first_embedding_text
    )
    assert (
        "분류: 가사소송 > 가,나,다류 가사소송"
        in first_embedding_text
    )

    first_stored_document = (
        vector_store.batches[0]["documents"][0]
    )

    assert first_stored_document["chunk_id"] == (
        "FORM-001::chunk-0000"
    )


def test_build_form_index_rejects_invalid_batch_size(
    tmp_path,
):
    parsed_file = tmp_path / "forms.json"
    parsed_file.write_text(
        "[]",
        encoding="utf-8",
    )

    try:
        build_form_index(
            parsed_file=parsed_file,
            embedding_service=FakeEmbeddingService(),
            vector_store=FakeVectorStore(),
            batch_size=0,
        )
    except ValueError as error:
        assert "batch_size" in str(error)
    else:
        raise AssertionError(
            "ValueError가 발생해야 합니다."
        )


class UniqueFakeVectorStore:
    def __init__(self):
        self.batches = []
        self.records = {}

    def upsert_documents(
        self,
        documents,
        embeddings,
    ):
        documents = list(documents)
        embeddings = list(embeddings)

        self.batches.append(
            {
                "documents": documents,
                "embeddings": embeddings,
            }
        )

        for document, embedding in zip(
            documents,
            embeddings,
        ):
            record_id = (
                document.get("chunk_id")
                or document["document_id"]
            )

            self.records[record_id] = {
                "document": document,
                "embedding": embedding,
            }

    def count(self):
        return len(self.records)


def test_build_form_index_reupserts_sync_batch(
    tmp_path,
):
    parsed_file = tmp_path / "forms.json"

    records = []

    for index in range(120):
        records.append(
            {
                "form_name": f"테스트 서식 {index}",
                "main": "가사소송",
                "sub": "기타",
                "tmpltNo": f"FORM-{index:03d}",
                "source_file": (
                    f"forms/form-{index:03d}.hwpx"
                ),
                "markdown": f"테스트 본문 {index}",
            }
        )

    parsed_file.write_text(
        json.dumps(
            records,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    embedding_service = FakeEmbeddingService()
    vector_store = UniqueFakeVectorStore()

    result = build_form_index(
        parsed_file=parsed_file,
        embedding_service=embedding_service,
        vector_store=vector_store,
        chunk_size=1000,
        chunk_overlap=100,
        batch_size=32,
        flush_upsert_size=100,
        flush_wait_seconds=0,
    )

    assert result == {
        "documents": 120,
        "chunks": 120,
        "stored": 120,
    }

    # 일반 색인 4회 + 동기화 재업서트 1회
    assert len(vector_store.batches) == 5

    flush_batch = vector_store.batches[-1]

    assert len(
        flush_batch["documents"]
    ) == 100

    assert flush_batch["documents"][0][
        "chunk_id"
    ] == "FORM-000::chunk-0000"
