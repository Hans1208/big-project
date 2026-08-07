from app.health.rag import (
    build_rag_health,
)
from app.main import app
from rag.config import (
    EMBEDDING_MODEL_NAME,
)


COLLECTION_COUNTS = {
    "legal_forms": 1264,
    "legal_statutes": 2289,
    "legal_precedents": 3480,
    "legal_consultations": 1996,
}


class FakeStore:
    def __init__(self, count):
        self._count = count

    def count(self):
        return self._count


def make_store_factory(
    counts,
    failures=None,
):
    failures = failures or {}

    def factory(collection_name):
        if collection_name in failures:
            raise failures[collection_name]

        return FakeStore(
            counts[collection_name]
        )

    return factory


def test_rag_health_is_ready_when_all_collections_have_data():
    status_code, payload = build_rag_health(
        store_factory=make_store_factory(
            COLLECTION_COUNTS
        )
    )

    assert status_code == 200
    assert payload == {
        "status": "ready",
        "embedding_model": (
            EMBEDDING_MODEL_NAME
        ),
        "collections": COLLECTION_COUNTS,
        "issues": [],
    }


def test_rag_health_is_degraded_when_a_collection_is_empty():
    counts = {
        **COLLECTION_COUNTS,
        "legal_consultations": 0,
    }

    status_code, payload = build_rag_health(
        store_factory=make_store_factory(
            counts
        )
    )

    assert status_code == 200
    assert payload["status"] == "degraded"
    assert payload["collections"] == counts
    assert payload["issues"] == [
        (
            "legal_consultations "
            "collection is empty"
        )
    ]


def test_rag_health_is_unavailable_when_chroma_check_fails():
    status_code, payload = build_rag_health(
        store_factory=make_store_factory(
            COLLECTION_COUNTS,
            failures={
                "legal_precedents": (
                    RuntimeError(
                        "chroma unavailable"
                    )
                )
            },
        )
    )

    assert status_code == 503
    assert payload["status"] == "unavailable"
    assert payload["collections"][
        "legal_precedents"
    ] is None
    assert payload["issues"] == [
        (
            "legal_precedents "
            "collection check failed: "
            "RuntimeError"
        )
    ]


def test_rag_health_route_is_registered():
    openapi_schema = app.openapi()

    assert (
        "/health/rag"
        in openapi_schema["paths"]
    )
    assert (
        "get"
        in openapi_schema["paths"][
            "/health/rag"
        ]
    )
