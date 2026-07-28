"""파싱된 법률 서식을 로컬 ChromaDB에 색인한다."""

from __future__ import annotations

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


def build_form_index(
    parsed_file: str | Path = PARSED_FORMS_PATH,
    persist_directory: str | Path = CHROMA_DB_DIR,
    collection_name: str = LEGAL_FORMS_COLLECTION_NAME,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
    batch_size: int = DEFAULT_BATCH_SIZE,
    embedding_service: Any | None = None,
    vector_store: Any | None = None,
) -> dict[str, int]:
    """서식을 로딩·청킹·임베딩하고 ChromaDB에 저장한다.

    Args:
        parsed_file:
            팀원이 생성한 parsed/전체.json 경로.
        persist_directory:
            ChromaDB 데이터 저장 폴더.
        collection_name:
            서식용 ChromaDB 컬렉션 이름.
        chunk_size:
            청크 최대 글자 수.
        chunk_overlap:
            인접 청크 간 중복 글자 수.
        batch_size:
            한 번에 임베딩하고 저장할 청크 수.
        embedding_service:
            테스트 또는 외부 주입용 임베딩 서비스.
        vector_store:
            테스트 또는 외부 주입용 벡터 저장소.

    Returns:
        원본 문서 수, 청크 수, 저장 레코드 수.
    """
    if batch_size < 1:
        raise ValueError(
            "batch_size는 1 이상이어야 합니다."
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

        print(
            "색인 진행:",
            f"{batch_number}/{total_batches}",
            f"({min(start + batch_size, len(chunks))}"
            f"/{len(chunks)} 청크)",
        )

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
