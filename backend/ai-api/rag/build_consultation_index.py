"""Build the family-law consultation vector index."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Any

from rag.config import (
    CHROMA_DB_DIR,
    LEGAL_CONSULTATIONS_COLLECTION_NAME,
    STORAGE_DIR,
)
from rag.consultation_documents import (
    build_consultation_chunks,
)
from rag.consultation_loader import (
    RawConsultationRow,
    load_all_consultation_sources,
)
from rag.consultation_normalizer import (
    normalize_consultations,
    write_normalized_outputs,
)
from rag.embedding_service import (
    EmbeddingService,
)
from rag.vector_store import (
    ChromaVectorStore,
)


DEFAULT_BATCH_SIZE = 32

DEFAULT_DATA_DIR = (
    STORAGE_DIR
    / "legal_consultations"
)

DEFAULT_RAW_DIR = (
    DEFAULT_DATA_DIR / "raw"
)

DEFAULT_PROCESSED_PATH = (
    DEFAULT_DATA_DIR
    / "processed"
    / "family_consultations.jsonl"
)

DEFAULT_REPORT_PATH = (
    DEFAULT_DATA_DIR
    / "reports"
    / "normalization_report.json"
)


def build_consultation_index(
    *,
    raw_dir: str | Path = (
        DEFAULT_RAW_DIR
    ),
    processed_path: str | Path = (
        DEFAULT_PROCESSED_PATH
    ),
    report_path: str | Path = (
        DEFAULT_REPORT_PATH
    ),
    source_rows: Sequence[
        RawConsultationRow
    ]
    | None = None,
    batch_size: int = (
        DEFAULT_BATCH_SIZE
    ),
    persist_directory: str | Path = (
        CHROMA_DB_DIR
    ),
    collection_name: str = (
        LEGAL_CONSULTATIONS_COLLECTION_NAME
    ),
    embedding_service: Any | None = None,
    vector_store: Any | None = None,
    reset_collection: bool = True,
) -> dict[str, int]:
    """Normalize, chunk, embed and store consultation records."""

    if batch_size < 1:
        raise ValueError(
            "batch_size must be at least 1."
        )

    rows = (
        list(source_rows)
        if source_rows is not None
        else load_all_consultation_sources(
            Path(raw_dir)
        )
    )

    consultations, report = (
        normalize_consultations(rows)
    )

    if not consultations:
        raise ValueError(
            "No normalized consultations "
            "were produced."
        )

    write_normalized_outputs(
        consultations,
        report,
        processed_path=Path(
            processed_path
        ),
        report_path=Path(
            report_path
        ),
    )

    chunks = (
        build_consultation_chunks(
            consultations
        )
    )

    if not chunks:
        raise ValueError(
            "No consultation chunks "
            "were produced."
        )

    if embedding_service is None:
        embedding_service = (
            EmbeddingService()
        )

    if vector_store is None:
        vector_store = (
            ChromaVectorStore(
                persist_directory=(
                    persist_directory
                ),
                collection_name=(
                    collection_name
                ),
            )
        )

    if reset_collection:
        clear_method = getattr(
            vector_store,
            "clear",
            None,
        )

        if clear_method is None:
            raise TypeError(
                "vector_store must provide "
                "clear()."
            )

        clear_method()

    total_batches = (
        len(chunks)
        + batch_size
        - 1
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
                    chunk[
                        "embedding_text"
                    ]
                    for chunk in batch
                ]
            )
        )

        vector_store.upsert_documents(
            documents=batch,
            embeddings=embeddings,
        )

        print(
            "Consultation index progress:",
            f"{batch_number}/{total_batches}",
            (
                f"({min(start + batch_size, len(chunks))}"
                f"/{len(chunks)} chunks)"
            ),
        )

    stored = int(
        vector_store.count()
    )

    if stored != len(chunks):
        raise RuntimeError(
            "Stored consultation count "
            "does not match generated chunks: "
            f"{stored} != {len(chunks)}"
        )

    return {
        "input_rows": int(
            report["input_rows"]
        ),
        "family_candidate_rows": int(
            report[
                "family_candidate_rows"
            ]
        ),
        "normalized_rows": int(
            report["normalized_rows"]
        ),
        "duplicate_rows": int(
            report["duplicate_rows"]
        ),
        "personal_information_candidates": (
            len(
                report[
                    "personal_information_candidates"
                ]
            )
        ),
        "chunks": len(chunks),
        "stored": stored,
    }


def main() -> None:
    print(
        "Loading family-law consultations."
    )

    result = (
        build_consultation_index()
    )

    print()
    print(
        "=== Consultation indexing complete ==="
    )
    print(
        "Input rows:",
        result["input_rows"],
    )
    print(
        "Family-law candidates:",
        result["family_candidate_rows"],
    )
    print(
        "Normalized consultations:",
        result["normalized_rows"],
    )
    print(
        "Duplicate rows:",
        result["duplicate_rows"],
    )
    print(
        "PII candidates:",
        result[
            "personal_information_candidates"
        ],
    )
    print(
        "Generated chunks:",
        result["chunks"],
    )
    print(
        "Stored records:",
        result["stored"],
    )
    print(
        "Collection:",
        LEGAL_CONSULTATIONS_COLLECTION_NAME,
    )
    print(
        "Storage path:",
        CHROMA_DB_DIR,
    )


if __name__ == "__main__":
    main()
