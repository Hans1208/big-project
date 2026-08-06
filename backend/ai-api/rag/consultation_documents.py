"""Prepare consultation records for embedding."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import asdict
from typing import Any

from rag.chunking import (
    DEFAULT_CHUNK_OVERLAP,
    DEFAULT_CHUNK_SIZE,
    chunk_documents,
)
from rag.consultation_normalizer import (
    NormalizedConsultation,
)


class ConsultationDocumentError(
    ValueError
):
    """Raised when a consultation cannot become a document."""


def _required_value(
    consultation: NormalizedConsultation,
    field_name: str,
) -> str:
    value = str(
        getattr(
            consultation,
            field_name,
            "",
        )
        or ""
    ).strip()

    if not value:
        raise ConsultationDocumentError(
            f"{field_name} is required."
        )

    return value


def prepare_consultation_document(
    consultation: NormalizedConsultation,
) -> dict[str, Any]:
    """Convert one normalized consultation into a RAG document."""

    consultation_id = _required_value(
        consultation,
        "consultation_id",
    )
    source_type = _required_value(
        consultation,
        "source_type",
    )
    service_category = _required_value(
        consultation,
        "service_category",
    )
    legal_path = _required_value(
        consultation,
        "legal_path",
    )
    question = _required_value(
        consultation,
        "question",
    )
    answer = _required_value(
        consultation,
        "answer",
    )

    document = asdict(
        consultation
    )

    document.update(
        {
            "document_id": (
                f"consultation:"
                f"{consultation_id}"
            ),
            "document_type": (
                "legal_consultation"
            ),
            "title": question,
            "content": answer,
            "case_type": (
                service_category
            ),
            "case_subtype": (
                source_type
            ),
            "source": (
                "Korea Legal Aid Corporation "
                "legal consultation"
            ),
            "consultation_id": (
                consultation_id
            ),
            "source_type": source_type,
            "service_category": (
                service_category
            ),
            "legal_path": legal_path,
            "question": question,
            "answer": answer,
        }
    )

    return document


def _build_consultation_embedding_text(
    chunk: dict[str, Any],
) -> str:
    legal_path = str(
        chunk.get(
            "legal_path",
            "",
        )
        or ""
    ).strip()

    question = str(
        chunk.get(
            "question",
            "",
        )
        or ""
    ).strip()

    content = str(
        chunk.get(
            "content",
            "",
        )
        or ""
    ).strip()

    return "\n".join(
        (
            f"\ubd84\ub958: {legal_path}",
            f"\uc9c8\ubb38: {question}",
            f"\ub2f5\ubcc0: {content}",
        )
    )


def build_consultation_chunks(
    consultations: Sequence[
        NormalizedConsultation
    ],
    chunk_size: int = (
        DEFAULT_CHUNK_SIZE
    ),
    chunk_overlap: int = (
        DEFAULT_CHUNK_OVERLAP
    ),
) -> list[dict[str, Any]]:
    """Convert normalized consultations into answer chunks."""

    documents = [
        prepare_consultation_document(
            consultation
        )
        for consultation in consultations
    ]

    chunks = chunk_documents(
        documents=documents,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )

    for chunk in chunks:
        chunk["embedding_text"] = (
            _build_consultation_embedding_text(
                chunk
            )
        )

    chunk_ids = [
        str(
            chunk.get(
                "chunk_id",
                "",
            )
        )
        for chunk in chunks
    ]

    if (
        len(chunk_ids)
        != len(set(chunk_ids))
    ):
        raise ConsultationDocumentError(
            "Duplicate consultation chunk_id found."
        )

    if any(
        not str(
            chunk.get(
                "content",
                "",
            )
        ).strip()
        for chunk in chunks
    ):
        raise ConsultationDocumentError(
            "Empty consultation chunk found."
        )

    return chunks
