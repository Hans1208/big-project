"""Build the current-statute vector index."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Any

from rag.config import (
    CHROMA_DB_DIR,
    LEGAL_STATUTES_COLLECTION_NAME,
)
from rag.embedding_service import EmbeddingService
from rag.statute_api import (
    LawApiClient,
    LawApiError,
)
from rag.statute_documents import (
    build_statute_chunks,
)
from rag.statute_parser import (
    parse_statute_payload,
)
from rag.vector_store import ChromaVectorStore


DEFAULT_BATCH_SIZE = 32

DEFAULT_STATUTE_NAMES: tuple[str, ...] = (
    "\ubbfc\ubc95",
    "\uac00\uc0ac\uc18c\uc1a1\ubc95",
    (
        "\uac00\uc871\uad00\uacc4\uc758 "
        "\ub4f1\ub85d \ub4f1\uc5d0 "
        "\uad00\ud55c \ubc95\ub960"
    ),
    "\ubbfc\uc0ac\uc18c\uc1a1\ubc95",
    "\ubbfc\uc0ac\uc9d1\ud589\ubc95",
)


def _find_exact_law(
    laws: Sequence[dict[str, str]],
    expected_name: str,
) -> dict[str, str]:
    normalized_name = expected_name.strip()

    for law in laws:
        if str(
            law.get("name", "")
        ).strip() == normalized_name:
            return law

    raise LawApiError(
        f"Exact statute was not found: "
        f"{normalized_name}"
    )


def build_statute_index(
    law_names: Sequence[str] = (
        DEFAULT_STATUTE_NAMES
    ),
    persist_directory: str | Path = (
        CHROMA_DB_DIR
    ),
    collection_name: str = (
        LEGAL_STATUTES_COLLECTION_NAME
    ),
    batch_size: int = DEFAULT_BATCH_SIZE,
    api_client: Any | None = None,
    embedding_service: Any | None = None,
    vector_store: Any | None = None,
) -> dict[str, int]:
    """Fetch, parse, embed, and store current statutes."""
    if batch_size < 1:
        raise ValueError(
            "batch_size must be at least 1."
        )

    clean_law_names = tuple(
        name.strip()
        for name in law_names
        if name.strip()
    )

    if not clean_law_names:
        raise ValueError(
            "At least one statute name is required."
        )

    if api_client is None:
        api_client = LawApiClient()

    if embedding_service is None:
        embedding_service = EmbeddingService()

    if vector_store is None:
        vector_store = ChromaVectorStore(
            persist_directory=persist_directory,
            collection_name=collection_name,
        )

    all_chunks: list[dict[str, Any]] = []
    total_articles = 0

    for law_name in clean_law_names:
        search_results = (
            api_client.search_current_laws(
                query=law_name,
                display=100,
                page=1,
            )
        )

        selected_law = _find_exact_law(
            search_results,
            law_name,
        )

        law_id = str(
            selected_law.get("law_id", "")
        ).strip()
        mst = str(
            selected_law.get("mst", "")
        ).strip()

        if not law_id:
            raise LawApiError(
                f"Statute ID is missing: "
                f"{law_name}"
            )

        payload = api_client.get_current_law(
            law_id=law_id
        )

        articles = parse_statute_payload(
            payload,
            mst=mst,
        )

        chunks = build_statute_chunks(
            articles
        )

        total_articles += len(articles)
        all_chunks.extend(chunks)

        print(
            "Law fetched:",
            law_name,
            f"articles={len(articles)}",
            f"chunks={len(chunks)}",
        )

    total_batches = (
        len(all_chunks) + batch_size - 1
    ) // batch_size

    for batch_number, start in enumerate(
        range(
            0,
            len(all_chunks),
            batch_size,
        ),
        start=1,
    ):
        batch = all_chunks[
            start:start + batch_size
        ]

        texts = [
            chunk["embedding_text"]
            for chunk in batch
        ]

        embeddings = (
            embedding_service.embed_documents(
                texts
            )
        )

        vector_store.upsert_documents(
            documents=batch,
            embeddings=embeddings,
        )

        stored_count = min(
            start + batch_size,
            len(all_chunks),
        )

        print(
            "Index progress:",
            f"{batch_number}/{total_batches}",
            (
                f"({stored_count}/"
                f"{len(all_chunks)} chunks)"
            ),
        )

    return {
        "laws": len(clean_law_names),
        "articles": total_articles,
        "chunks": len(all_chunks),
        "stored": vector_store.count(),
    }


def main() -> None:
    """Build the configured current-statute index."""
    print("Loading current statutes.")

    result = build_statute_index()

    print()
    print(
        "=== Statute indexing complete ==="
    )
    print("Statutes:", result["laws"])
    print("Source articles:", result["articles"])
    print("Generated chunks:", result["chunks"])
    print("Stored records:", result["stored"])
    print(
        "Collection:",
        LEGAL_STATUTES_COLLECTION_NAME,
    )
    print("Storage path:", CHROMA_DB_DIR)


if __name__ == "__main__":
    main()
