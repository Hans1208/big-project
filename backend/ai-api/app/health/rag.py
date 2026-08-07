"""Readiness checks for the local RAG infrastructure."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from rag.config import (
    CHROMA_DB_DIR,
    EMBEDDING_MODEL_NAME,
    LEGAL_CONSULTATIONS_COLLECTION_NAME,
    LEGAL_FORMS_COLLECTION_NAME,
    LEGAL_PRECEDENTS_COLLECTION_NAME,
    LEGAL_STATUTES_COLLECTION_NAME,
)
from rag.vector_store import ChromaVectorStore


router = APIRouter(
    prefix="/health",
    tags=["health"],
)

RAG_COLLECTION_NAMES = (
    LEGAL_FORMS_COLLECTION_NAME,
    LEGAL_STATUTES_COLLECTION_NAME,
    LEGAL_PRECEDENTS_COLLECTION_NAME,
    LEGAL_CONSULTATIONS_COLLECTION_NAME,
)

StoreFactory = Callable[
    [str],
    Any,
]


def _default_store_factory(
    collection_name: str,
) -> ChromaVectorStore:
    return ChromaVectorStore(
        persist_directory=CHROMA_DB_DIR,
        collection_name=collection_name,
    )


def build_rag_health(
    *,
    store_factory: StoreFactory = (
        _default_store_factory
    ),
) -> tuple[int, dict[str, Any]]:
    """Return HTTP status and RAG readiness details."""

    collection_counts: dict[
        str,
        int | None,
    ] = {}

    issues: list[str] = []
    unavailable = False

    for collection_name in (
        RAG_COLLECTION_NAMES
    ):
        try:
            store = store_factory(
                collection_name
            )
            count = int(
                store.count()
            )
        except Exception as exc:
            collection_counts[
                collection_name
            ] = None

            issues.append(
                f"{collection_name} "
                "collection check failed: "
                f"{type(exc).__name__}"
            )

            unavailable = True
            continue

        collection_counts[
            collection_name
        ] = count

        if count == 0:
            issues.append(
                f"{collection_name} "
                "collection is empty"
            )

    if unavailable:
        status_code = 503
        status = "unavailable"
    elif issues:
        status_code = 200
        status = "degraded"
    else:
        status_code = 200
        status = "ready"

    return status_code, {
        "status": status,
        "embedding_model": (
            EMBEDDING_MODEL_NAME
        ),
        "collections": (
            collection_counts
        ),
        "issues": issues,
    }


@router.get("/rag")
def rag_health() -> JSONResponse:
    status_code, payload = (
        build_rag_health()
    )

    return JSONResponse(
        status_code=status_code,
        content=payload,
    )
