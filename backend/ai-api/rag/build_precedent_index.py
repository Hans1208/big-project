"""Build the family-law precedent vector index."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date
from pathlib import Path
from typing import Any

from rag.config import (
    CHROMA_DB_DIR,
    LEGAL_PRECEDENTS_COLLECTION_NAME,
)
from rag.embedding_service import EmbeddingService
from rag.precedent_api import (
    PrecedentApiClient,
    PrecedentApiError,
)
from rag.precedent_collector import (
    PrecedentSearchJob,
    build_default_search_jobs,
    collect_precedent_summaries,
)
from rag.precedent_documents import (
    build_precedent_chunks,
)
from rag.precedent_parser import (
    PrecedentParseError,
    parse_precedent_payload,
)
from rag.vector_store import ChromaVectorStore


DEFAULT_BATCH_SIZE = 32
DEFAULT_START_DATE = "20160101"


def build_precedent_index(
    *,
    jobs: Sequence[PrecedentSearchJob] | None = None,
    decision_date_from: str = DEFAULT_START_DATE,
    decision_date_to: str | None = None,
    display: int = 100,
    max_pages_per_job: int | None = None,
    batch_size: int = DEFAULT_BATCH_SIZE,
    persist_directory: str | Path = CHROMA_DB_DIR,
    collection_name: str = (
        LEGAL_PRECEDENTS_COLLECTION_NAME
    ),
    api_client: Any | None = None,
    embedding_service: Any | None = None,
    vector_store: Any | None = None,
) -> dict[str, int]:
    """Collect, parse, embed and store relevant precedents."""
    if batch_size < 1:
        raise ValueError(
            "batch_size must be at least 1."
        )

    if jobs is None:
        jobs = build_default_search_jobs()

    clean_jobs = list(jobs)

    if not clean_jobs:
        raise ValueError(
            "At least one search job is required."
        )

    if decision_date_to is None:
        decision_date_to = (
            date.today().strftime("%Y%m%d")
        )

    if api_client is None:
        api_client = PrecedentApiClient()

    if embedding_service is None:
        embedding_service = EmbeddingService()

    if vector_store is None:
        vector_store = ChromaVectorStore(
            persist_directory=persist_directory,
            collection_name=collection_name,
        )

    summaries = collect_precedent_summaries(
        client=api_client,
        jobs=clean_jobs,
        decision_date_from=decision_date_from,
        decision_date_to=decision_date_to,
        display=display,
        max_pages_per_job=max_pages_per_job,
    )

    precedents: list[dict[str, Any]] = []
    failed = 0

    for index, summary in enumerate(
        summaries,
        start=1,
    ):
        precedent_id = str(
            summary.get(
                "precedent_id",
                "",
            )
        ).strip()

        try:
            payload = api_client.get_precedent(
                precedent_id=precedent_id,
            )

            precedent = parse_precedent_payload(
                payload,
                list_item=summary,
                matched_searches=summary.get(
                    "matched_searches",
                    [],
                ),
            )
        except (
            PrecedentApiError,
            PrecedentParseError,
            ValueError,
        ) as error:
            failed += 1

            print(
                "Precedent skipped:",
                precedent_id,
                type(error).__name__,
            )
            continue

        precedents.append(precedent)

        print(
            "Detail fetched:",
            f"{index}/{len(summaries)}",
            precedent_id,
            precedent["case_name"],
        )

    chunks = build_precedent_chunks(
        precedents
    ) if precedents else []

    total_batches = (
        len(chunks) + batch_size - 1
    ) // batch_size

    for batch_number, start in enumerate(
        range(
            0,
            len(chunks),
            batch_size,
        ),
        start=1,
    ):
        batch = chunks[
            start:start + batch_size
        ]

        embeddings = (
            embedding_service.embed_documents(
                [
                    chunk["embedding_text"]
                    for chunk in batch
                ]
            )
        )

        vector_store.upsert_documents(
            documents=batch,
            embeddings=embeddings,
        )

        print(
            "Index progress:",
            f"{batch_number}/{total_batches}",
            (
                f"({min(start + batch_size, len(chunks))}"
                f"/{len(chunks)} chunks)"
            ),
        )

    return {
        "jobs": len(clean_jobs),
        "summaries": len(summaries),
        "precedents": len(precedents),
        "failed": failed,
        "chunks": len(chunks),
        "stored": vector_store.count(),
    }


def main() -> None:
    print("Loading relevant precedents.")

    result = build_precedent_index()

    print()
    print("=== Precedent indexing complete ===")
    print("Search jobs:", result["jobs"])
    print("Unique summaries:", result["summaries"])
    print("Parsed precedents:", result["precedents"])
    print("Failed details:", result["failed"])
    print("Generated chunks:", result["chunks"])
    print("Stored records:", result["stored"])
    print(
        "Collection:",
        LEGAL_PRECEDENTS_COLLECTION_NAME,
    )
    print("Storage path:", CHROMA_DB_DIR)


if __name__ == "__main__":
    main()