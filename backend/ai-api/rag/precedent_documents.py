"""Prepare precedent sections for embedding and retrieval."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from rag.chunking import (
    DEFAULT_CHUNK_OVERLAP,
    DEFAULT_CHUNK_SIZE,
    chunk_documents,
)


class PrecedentDocumentError(ValueError):
    """Raised when a precedent cannot become a search document."""


SECTION_FIELDS = (
    (
        "holding",
        "holding",
        "판시사항",
    ),
    (
        "summary",
        "summary",
        "판결요지",
    ),
    (
        "full_text",
        "full_text",
        "판례내용",
    ),
)


def prepare_precedent_documents(
    precedent: dict[str, Any],
) -> list[dict[str, Any]]:
    """Create one RAG document for each available section."""
    precedent_id = str(
        precedent.get(
            "precedent_id",
            "",
        )
    ).strip()
    case_name = str(
        precedent.get(
            "case_name",
            "",
        )
    ).strip()

    if not precedent_id:
        raise PrecedentDocumentError(
            "precedent_id is required."
        )

    if not case_name:
        raise PrecedentDocumentError(
            "case_name is required."
        )

    documents: list[dict[str, Any]] = []

    for (
        section_type,
        field_name,
        section_label,
    ) in SECTION_FIELDS:
        content = str(
            precedent.get(
                field_name,
                "",
            )
        ).strip()

        if not content:
            continue

        document = dict(precedent)

        document.update(
            {
                "document_id": (
                    f"precedent:{precedent_id}:"
                    f"{section_type}"
                ),
                "document_type": (
                    "legal_precedent"
                ),
                "title": (
                    f"{case_name} "
                    f"[{section_label}]"
                ),
                "content": content,
                "case_type": str(
                    precedent.get(
                        "case_type_name",
                        "",
                    )
                ).strip(),
                "case_subtype": (
                    section_label
                ),
                "section_type": section_type,
                "section_label": section_label,
            }
        )

        documents.append(document)

    if not documents:
        raise PrecedentDocumentError(
            "precedent has no searchable sections."
        )

    return documents


def _build_precedent_embedding_text(
    chunk: dict[str, Any],
) -> str:
    fields = (
        (
            "사건명",
            chunk.get("case_name", ""),
        ),
        (
            "사건번호",
            chunk.get("case_number", ""),
        ),
        (
            "법원",
            chunk.get("court_name", ""),
        ),
        (
            "법원등급",
            chunk.get("court_level", ""),
        ),
        (
            "선고일자",
            chunk.get("decision_date", ""),
        ),
        (
            "사건종류",
            chunk.get("case_type_name", ""),
        ),
        (
            "문서구성",
            chunk.get("section_label", ""),
        ),
        (
            "참조조문",
            chunk.get(
                "referenced_statutes",
                "",
            ),
        ),
    )

    lines = [
        f"{label}: {str(value).strip()}"
        for label, value in fields
        if str(value).strip()
    ]

    lines.append(
        str(
            chunk.get(
                "content",
                "",
            )
        ).strip()
    )

    return "\n".join(lines)


def build_precedent_chunks(
    precedents: Sequence[dict[str, Any]],
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> list[dict[str, Any]]:
    """Prepare and split precedent sections into RAG chunks."""
    documents: list[dict[str, Any]] = []

    for precedent in precedents:
        documents.extend(
            prepare_precedent_documents(
                precedent
            )
        )

    chunks = chunk_documents(
        documents=documents,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )

    for chunk in chunks:
        chunk["embedding_text"] = (
            _build_precedent_embedding_text(
                chunk
            )
        )

    return chunks