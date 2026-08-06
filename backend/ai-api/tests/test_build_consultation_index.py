from __future__ import annotations

from pathlib import Path

import pytest

from rag.build_consultation_index import (
    build_consultation_index,
)
from rag.config import (
    LEGAL_CONSULTATIONS_COLLECTION_NAME,
)
from rag.consultation_loader import (
    RawConsultationRow,
)
from rag.consultation_normalizer import (
    PersonalInformationDetectedError,
)
from rag.vector_store import (
    ChromaVectorStore,
)


def _row(
    *,
    source_row: int,
    source_type: str = "basic",
    legal_path: str,
    question: str,
    answer: str,
) -> RawConsultationRow:
    return RawConsultationRow(
        source_key="test",
        source_type=source_type,
        source_file="test.csv",
        source_row=source_row,
        legal_path=legal_path,
        question=question,
        answer=answer,
    )


class FakeEmbeddingService:
    def __init__(self):
        self.batches = []

    def embed_documents(self, texts):
        clean_texts = list(texts)
        self.batches.append(clean_texts)

        return [
            [1.0, 0.0]
            for _ in clean_texts
        ]


class FakeVectorStore:
    def __init__(self):
        self.documents = []
        self.embeddings = []
        self.clear_calls = 0

    def clear(self):
        self.clear_calls += 1
        self.documents.clear()
        self.embeddings.clear()

    def upsert_documents(
        self,
        documents,
        embeddings,
    ):
        self.documents.extend(
            documents
        )
        self.embeddings.extend(
            embeddings
        )

    def count(self):
        return len(self.documents)


def test_consultation_collection_name_is_separate():
    assert (
        LEGAL_CONSULTATIONS_COLLECTION_NAME
        == "legal_consultations"
    )


def test_build_index_normalizes_chunks_and_stores(
    tmp_path: Path,
):
    rows = [
        _row(
            source_row=2,
            source_type="case",
            legal_path=(
                "\uc0c1\uc18d\uacfc\uc720\uc5b8>"
                "\uc0c1\uc18d\ud3ec\uae30"
            ),
            question=(
                "\ube5a\uc744 \ub0a8\uae34 "
                "\ubd80\ubaa8\ub2d8\uc774 "
                "\uc0ac\ub9dd\ud588\uc2b5\ub2c8\ub2e4."
            ),
            answer=(
                "\uc0c1\uc18d\uac1c\uc2dc\ub97c "
                "\uc548 \ub0a0\ubd80\ud130 "
                "3\uac1c\uc6d4 \uc548\uc5d0 "
                "\uc0c1\uc18d\ud3ec\uae30\ub97c "
                "\uc2e0\uace0\ud560 \uc218 "
                "\uc788\uc2b5\ub2c8\ub2e4."
            ),
        ),
        _row(
            source_row=3,
            legal_path=(
                "\uac00\uc871\uad00\uacc4\ub4f1\ub85d>"
                "\uac1c\uba85"
            ),
            question=(
                "\uc774\ub984\uc744 "
                "\ubc14\uafb8\uace0 \uc2f6\uc5b4\uc694."
            ),
            answer=(
                "\uad00\ud560 \uac00\uc815\ubc95\uc6d0\uc758 "
                "\ud5c8\uac00\uac00 "
                "\ud544\uc694\ud569\ub2c8\ub2e4."
            ),
        ),
    ]

    embedding_service = (
        FakeEmbeddingService()
    )
    vector_store = FakeVectorStore()

    result = build_consultation_index(
        source_rows=rows,
        processed_path=(
            tmp_path / "processed.jsonl"
        ),
        report_path=(
            tmp_path / "report.json"
        ),
        batch_size=1,
        embedding_service=(
            embedding_service
        ),
        vector_store=vector_store,
    )

    assert result == {
        "input_rows": 2,
        "family_candidate_rows": 2,
        "normalized_rows": 2,
        "duplicate_rows": 0,
        "personal_information_candidates": 0,
        "chunks": 2,
        "stored": 2,
    }

    assert vector_store.clear_calls == 1
    assert len(
        embedding_service.batches
    ) == 2
    assert len(
        vector_store.documents
    ) == 2

    assert all(
        document["embedding_text"]
        for document
        in vector_store.documents
    )

    assert all(
        not document[
            "embedding_text"
        ].startswith("passage:")
        for document
        in vector_store.documents
    )


def test_build_index_rejects_invalid_batch_size(
    tmp_path: Path,
):
    with pytest.raises(
        ValueError,
        match="batch_size",
    ):
        build_consultation_index(
            source_rows=[],
            processed_path=(
                tmp_path / "processed.jsonl"
            ),
            report_path=(
                tmp_path / "report.json"
            ),
            batch_size=0,
            embedding_service=(
                FakeEmbeddingService()
            ),
            vector_store=(
                FakeVectorStore()
            ),
        )


def test_build_index_rejects_no_family_records(
    tmp_path: Path,
):
    rows = [
        _row(
            source_row=2,
            legal_path="\ubbfc\uc0ac>\uacc4\uc57d",
            question="\uacc4\uc57d \uc9c8\ubb38",
            answer="\uacc4\uc57d \ub2f5\ubcc0",
        )
    ]

    vector_store = FakeVectorStore()

    with pytest.raises(
        ValueError,
        match="No normalized consultations",
    ):
        build_consultation_index(
            source_rows=rows,
            processed_path=(
                tmp_path / "processed.jsonl"
            ),
            report_path=(
                tmp_path / "report.json"
            ),
            embedding_service=(
                FakeEmbeddingService()
            ),
            vector_store=vector_store,
        )

    assert vector_store.clear_calls == 0


def test_build_index_stops_before_embedding_on_pii(
    tmp_path: Path,
):
    rows = [
        _row(
            source_row=2,
            legal_path=(
                "\uce5c\uc871>\ubd80\uc591"
            ),
            question=(
                "\uc5f0\ub77d\ucc98\ub294 "
                "010-1234-5678"
            ),
            answer="\ubd80\uc591 \ub2f5\ubcc0",
        )
    ]

    embedding_service = (
        FakeEmbeddingService()
    )
    vector_store = FakeVectorStore()

    with pytest.raises(
        PersonalInformationDetectedError,
    ):
        build_consultation_index(
            source_rows=rows,
            processed_path=(
                tmp_path / "processed.jsonl"
            ),
            report_path=(
                tmp_path / "report.json"
            ),
            embedding_service=(
                embedding_service
            ),
            vector_store=vector_store,
        )

    assert embedding_service.batches == []
    assert vector_store.clear_calls == 0


def test_vector_store_preserves_consultation_metadata(
    tmp_path: Path,
):
    store = ChromaVectorStore(
        persist_directory=(
            tmp_path / "chroma"
        ),
        collection_name=(
            "legal_consultations"
        ),
    )

    document = {
        "document_id": (
            "consultation:"
            "consultation-0123456789abcdef01234567"
        ),
        "chunk_id": (
            "consultation:"
            "consultation-0123456789abcdef01234567"
            "::chunk-0000"
        ),
        "chunk_index": 0,
        "document_type": (
            "legal_consultation"
        ),
        "title": (
            "\uc0c1\uc18d\uc744 "
            "\ud3ec\uae30\ud558\uace0 "
            "\uc2f6\uc5b4\uc694."
        ),
        "content": (
            "\uc0c1\uc18d\ud3ec\uae30\ub97c "
            "\uc2e0\uace0\ud560 \uc218 "
            "\uc788\uc2b5\ub2c8\ub2e4."
        ),
        "source": (
            "Korea Legal Aid Corporation "
            "legal consultation"
        ),
        "case_type": "inheritance",
        "case_subtype": "case",
        "consultation_id": (
            "consultation-"
            "0123456789abcdef01234567"
        ),
        "source_type": "case",
        "service_category": (
            "inheritance"
        ),
        "legal_path": (
            "\uc0c1\uc18d\uacfc\uc720\uc5b8>"
            "\uc0c1\uc18d\ud3ec\uae30"
        ),
        "question": (
            "\uc0c1\uc18d\uc744 "
            "\ud3ec\uae30\ud558\uace0 "
            "\uc2f6\uc5b4\uc694."
        ),
        "answer": (
            "\uc0c1\uc18d\ud3ec\uae30\ub97c "
            "\uc2e0\uace0\ud560 \uc218 "
            "\uc788\uc2b5\ub2c8\ub2e4."
        ),
        "source_file": (
            "case_qa_part1_20240731.csv"
        ),
        "source_row": 42,
        "source_date": "2024-07-31",
    }

    store.upsert_documents(
        documents=[document],
        embeddings=[[1.0, 0.0]],
    )

    result = store.search(
        query_embedding=[1.0, 0.0],
        top_k=1,
    )[0]

    assert result["consultation_id"] == (
        document["consultation_id"]
    )
    assert result["source_type"] == "case"
    assert result["service_category"] == (
        "inheritance"
    )
    assert result["legal_path"] == (
        document["legal_path"]
    )
    assert result["question"] == (
        document["question"]
    )
    assert result["answer"] == (
        document["answer"]
    )
    assert result["source_file"] == (
        document["source_file"]
    )
    assert result["source_row"] == "42"
    assert result["source_date"] == (
        "2024-07-31"
    )


def test_clear_removes_only_target_collection_records(
    tmp_path: Path,
):
    persist_directory = (
        tmp_path / "chroma"
    )

    forms_store = ChromaVectorStore(
        persist_directory=(
            persist_directory
        ),
        collection_name="legal_forms",
    )

    forms_store.upsert_documents(
        documents=[
            {
                "document_id": "form:1",
                "content": "\uc11c\uc2dd \ubcf8\ubb38",
            }
        ],
        embeddings=[[1.0, 0.0]],
    )

    consultation_store = (
        ChromaVectorStore(
            persist_directory=(
                persist_directory
            ),
            collection_name=(
                "legal_consultations"
            ),
        )
    )

    consultation_store.upsert_documents(
        documents=[
            {
                "document_id": (
                    "consultation:1"
                ),
                "content": (
                    "\uc0c1\ub2f4 \ubcf8\ubb38"
                ),
            }
        ],
        embeddings=[[1.0, 0.0]],
    )

    consultation_store.clear()

    assert consultation_store.count() == 0
    assert forms_store.count() == 1
