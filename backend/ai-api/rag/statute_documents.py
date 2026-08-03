"""Prepare statute articles for embedding and retrieval."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from rag.chunking import (
    DEFAULT_CHUNK_OVERLAP,
    DEFAULT_CHUNK_SIZE,
    chunk_documents,
)


class StatuteDocumentError(ValueError):
    """Raised when an article cannot become a search document."""


def _build_article_heading(
    article: dict[str, Any],
) -> str:
    article_label = str(
        article.get("article_label", "")
    ).strip()

    article_title = str(
        article.get("article_title", "")
    ).strip()

    if not article_label:
        raise StatuteDocumentError(
            "article_label is required."
        )

    if article_title:
        return (
            f"{article_label}"
            f"({article_title})"
        )

    return article_label


def prepare_statute_document(
    article: dict[str, Any],
) -> dict[str, Any]:
    """Convert one parsed article to the common RAG shape."""
    document_id = str(
        article.get("document_id", "")
    ).strip()

    law_name = str(
        article.get("law_name", "")
    ).strip()

    text = str(
        article.get("text", "")
    ).strip()

    if not document_id:
        raise StatuteDocumentError(
            "document_id is required."
        )

    if not law_name:
        raise StatuteDocumentError(
            "law_name is required."
        )

    if not text:
        raise StatuteDocumentError(
            "article text is required."
        )

    article_heading = _build_article_heading(
        article
    )

    document = dict(article)

    document.update(
        {
            "document_type": "legal_statute",
            "title": (
                f"{law_name} {article_heading}"
            ),
            "content": text,
            "case_type": "",
            "case_subtype": "",
        }
    )

    return document


def _build_statute_embedding_text(
    chunk: dict[str, Any],
) -> str:
    law_name = str(
        chunk.get("law_name", "")
    ).strip()

    article_heading = _build_article_heading(
        chunk
    )

    content = str(
        chunk.get("content", "")
    ).strip()

    return "\n".join(
        (
            f"\ubc95\ub839\uba85: {law_name}",
            f"\uc870\ubb38: {article_heading}",
            content,
        )
    )


def build_statute_chunks(
    articles: Sequence[dict[str, Any]],
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> list[dict[str, Any]]:
    """Prepare and split statute articles into RAG chunks."""
    prepared_documents = [
        prepare_statute_document(article)
        for article in articles
    ]

    chunks = chunk_documents(
        documents=prepared_documents,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )

    for chunk in chunks:
        chunk["embedding_text"] = (
            _build_statute_embedding_text(
                chunk
            )
        )

    return chunks
