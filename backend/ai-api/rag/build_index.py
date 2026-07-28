"""파싱된 법률 서식을 로컬 ChromaDB에 색인한다."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from rag.chunking import (
    DEFAULT_CHUNK_OVERLAP,
    DEFAULT_CHUNK_SIZE,
    chunk_documents,
)
from rag.config import (
    CHROMA_DB_DIR,
    LEGAL_FORMS_COLLECTION_NAME,
    PARSED_FORMS_PATH,
)
from rag.embedding_service import EmbeddingService
from rag.form_loader import load_form_documents
from rag.vector_store import ChromaVectorStore


DEFAULT_BATCH_SIZE = 32

# ChromaDB Persistent HNSW 동기화를 유도하기 위해
# 색인 마지막에 동일 레코드를 다시 upsert하는 개수.
DEFAULT_FLUSH_UPSERT_SIZE = 100
DEFAULT_FLUSH_WAIT_SECONDS = 5.0


def build_form_index(
    parsed_file: str | Path = PARSED_FORMS_PATH,
    persist_directory: str | Path = CHROMA_DB_DIR,
    collection_name: str = LEGAL_FORMS_COLLECTION_NAME,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
    batch_size: int = DEFAULT_BATCH_SIZE,
    flush_upsert_size: int = DEFAULT_FLUSH_UPSERT_SIZE,
    flush_wait_seconds: float = DEFAULT_FLUSH_WAIT_SECONDS,
    embedding_service: Any | None = None,
    vector_store: Any | None = None,
) -> dict[str, int]:
    """서식을 로딩·청킹·임베딩하고 ChromaDB에 저장한다."""
    if batch_size < 1:
        raise ValueError(
            "batch_size는 1 이상이어야 합니다."
        )

    if flush_upsert_size < 0:
        raise ValueError(
            "flush_upsert_size는 0 이상이어야 합니다."
        )

    if flush_wait_seconds < 0:
        raise ValueError(
            "flush_wait_seconds는 0 이상이어야 합니다."
        )

    documents = load_form_documents(
        parsed_file
    )

    chunks = chunk_documents(
        documents=documents,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )

    if embedding_service is None:
        embedding_service = EmbeddingService()

    if vector_store is None:
        vector_store = ChromaVectorStore(
            persist_directory=persist_directory,
            collection_name=collection_name,
        )

    total_batches = (
        len(chunks) + batch_size - 1
    ) // batch_size

    flush_documents: list[dict[str, Any]] = []
    flush_embeddings: list[list[float]] = []

    for batch_number, start in enumerate(
        range(0, len(chunks), batch_size),
        start=1,
    ):
        batch = chunks[
            start:start + batch_size
        ]

        embedding_texts = [
            chunk["embedding_text"]
            for chunk in batch
        ]

        embeddings = (
            embedding_service.embed_documents(
                embedding_texts
            )
        )

        vector_store.upsert_documents(
            documents=batch,
            embeddings=embeddings,
        )

        remaining_flush_items = (
            flush_upsert_size
            - len(flush_documents)
        )

        if remaining_flush_items > 0:
            flush_documents.extend(
                batch[:remaining_flush_items]
            )
            flush_embeddings.extend(
                embeddings[:remaining_flush_items]
            )

        print(
            "색인 진행:",
            f"{batch_number}/{total_batches}",
            f"({min(start + batch_size, len(chunks))}"
            f"/{len(chunks)} 청크)",
        )

    should_flush = (
        flush_upsert_size > 0
        and len(flush_documents)
        >= flush_upsert_size
    )

    if should_flush:
        print(
            "HNSW 영속 동기화를 위해",
            f"{flush_upsert_size}개 청크를 재기록합니다.",
        )

        vector_store.upsert_documents(
            documents=flush_documents,
            embeddings=flush_embeddings,
        )

        if flush_wait_seconds > 0:
            time.sleep(
                flush_wait_seconds
            )

        print("HNSW 동기화용 재기록 완료")

    return {
        "documents": len(documents),
        "chunks": len(chunks),
        "stored": vector_store.count(),
    }


def main() -> None:
    """CLI에서 실제 법률 서식 색인을 실행한다."""
    print(
        "법률 서식 데이터를 불러오고 있습니다."
    )

    result = build_form_index()

    print()
    print("=== 법률 서식 색인 완료 ===")
    print(
        "원본 서식 수:",
        result["documents"],
    )
    print(
        "생성 청크 수:",
        result["chunks"],
    )
    print(
        "ChromaDB 저장 수:",
        result["stored"],
    )
    print(
        "컬렉션:",
        LEGAL_FORMS_COLLECTION_NAME,
    )
    print(
        "저장 위치:",
        CHROMA_DB_DIR,
    )


if __name__ == "__main__":
    main()
