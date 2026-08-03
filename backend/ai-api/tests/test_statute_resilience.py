from types import SimpleNamespace

import pytest

from app.ai.statutes.service import (
    build_statute_query,
    find_related_statutes,
)
from rag.build_statute_index import (
    build_statute_index,
)
from rag.statute_api import LawApiError


def empty_analysis():
    return SimpleNamespace(
        summary=None,
        case_type=None,
        case_subtype=None,
        extracted=None,
    )


def test_empty_consult_section_labels_do_not_trigger_search():
    fallback_text = (
        "[\uc694\uc57d]\n\n"
        "[\uc0c1\uc138]\n\n"
        "[\ucd94\ucd9c\ub41c "
        "\ucca8\ubd80\ub0b4\uc6a9]\n"
    )

    query = build_statute_query(
        analysis=empty_analysis(),
        fallback_text=fallback_text,
    )

    assert query == ""


def test_find_related_statutes_returns_empty_when_index_unavailable():
    calls = []

    def failing_search(**kwargs):
        calls.append(kwargs)

        raise RuntimeError(
            "Collection legal_statutes "
            "does not exist."
        )

    results = find_related_statutes(
        analysis=empty_analysis(),
        fallback_text="\uc7ac\uc0b0\ubd84\ud560",
        top_n=3,
        search=failing_search,
    )

    assert len(calls) == 1
    assert results == []


class FailingLawApiClient:
    def __init__(self):
        self.search_calls = []
        self.detail_calls = []

    def search_current_laws(
        self,
        query,
        display=100,
        page=1,
    ):
        self.search_calls.append(query)

        if query == "\ubbfc\ubc95":
            return [
                {
                    "law_id": "001706",
                    "mst": "284415",
                    "name": "\ubbfc\ubc95",
                }
            ]

        raise LawApiError(
            "temporary law API outage"
        )

    def get_current_law(self, law_id):
        self.detail_calls.append(law_id)

        return {
            "\ubc95\ub839": {
                "\ubc95\ub839\ud0a4": (
                    "0017062026031721454"
                ),
                "\uae30\ubcf8\uc815\ubcf4": {
                    "\ubc95\ub839ID": "001706",
                    "\ubc95\ub839\uba85_\ud55c\uae00": (
                        "\ubbfc\ubc95"
                    ),
                    "\uc2dc\ud589\uc77c\uc790": (
                        "20260317"
                    ),
                    "\ubc95\uc885\uad6c\ubd84": {
                        "content": "\ubc95\ub960",
                    },
                    "\uc18c\uad00\ubd80\ucc98": {
                        "content": "\ubc95\ubb34\ubd80",
                    },
                },
                "\uc870\ubb38": {
                    "\uc870\ubb38\ub2e8\uc704": [
                        {
                            "\uc870\ubb38\ud0a4": "10001",
                            "\uc870\ubb38\ubc88\ud638": "1",
                            "\uc870\ubb38\uc5ec\ubd80": (
                                "\uc870\ubb38"
                            ),
                            "\uc870\ubb38\uc81c\ubaa9": (
                                "\ubc95\uc6d0"
                            ),
                            "\uc870\ubb38\ub0b4\uc6a9": (
                                "\uc81c1\uc870"
                                "(\ubc95\uc6d0)"
                            ),
                        }
                    ]
                },
            }
        }


class RecordingEmbeddingService:
    def __init__(self):
        self.batches = []

    def embed_documents(self, texts):
        self.batches.append(list(texts))

        return [
            [1.0, 0.0]
            for _ in texts
        ]


class ExistingVectorStore:
    def __init__(self):
        self.existing_count = 7
        self.documents = []

    def upsert_documents(
        self,
        documents,
        embeddings,
    ):
        self.documents.extend(documents)

    def count(self):
        return (
            self.existing_count
            + len(self.documents)
        )


def test_api_failure_does_not_write_partial_index():
    api_client = FailingLawApiClient()
    embedding_service = (
        RecordingEmbeddingService()
    )
    vector_store = ExistingVectorStore()

    with pytest.raises(
        LawApiError,
        match="temporary law API outage",
    ):
        build_statute_index(
            law_names=(
                "\ubbfc\ubc95",
                "\uac00\uc0ac\uc18c\uc1a1\ubc95",
            ),
            batch_size=2,
            api_client=api_client,
            embedding_service=(
                embedding_service
            ),
            vector_store=vector_store,
        )

    assert api_client.search_calls == [
        "\ubbfc\ubc95",
        "\uac00\uc0ac\uc18c\uc1a1\ubc95",
    ]
    assert api_client.detail_calls == [
        "001706",
    ]

    assert embedding_service.batches == []
    assert vector_store.documents == []
    assert vector_store.count() == 7
