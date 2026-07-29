"""Build the legal-form vector index."""

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
    """Load, chunk, embed, and store parsed legal forms."""
    if batch_size < 1:
        raise ValueError(
            "batch_size must be at least 1."
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

        stored_count = min(
            start + batch_size,
            len(chunks),
        )

        print(
            "Index progress:",
            f"{batch_number}/{total_batches}",
            f"({stored_count}/{len(chunks)} chunks)",
        )

    return {
        "documents": len(documents),
        "chunks": len(chunks),
        "stored": vector_store.count(),
    }


def main() -> None:
    """Build the real legal-form index."""
    print("Loading legal forms.")

    result = build_form_index()

    print()
    print("=== Legal form indexing complete ===")
    print("Source documents:", result["documents"])
    print("Generated chunks:", result["chunks"])
    print("Stored records:", result["stored"])
    print("Collection:", LEGAL_FORMS_COLLECTION_NAME)
    print("Storage path:", CHROMA_DB_DIR)


if __name__ == "__main__":
    main()
