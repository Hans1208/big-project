from rag import config
from rag.vector_store import ChromaVectorStore


def sample_statute_chunk():
    return {
        "document_id": "statute:001706:839:2",
        "chunk_id": (
            "statute:001706:839:2::chunk-0000"
        ),
        "chunk_index": 0,
        "document_type": "legal_statute",
        "title": (
            "\ubbfc\ubc95 "
            "\uc81c839\uc870\uc7582"
            "(\uc7ac\uc0b0\ubd84\ud560\uccad\uad6c\uad8c)"
        ),
        "content": (
            "\ud611\uc758\uc0c1 \uc774\ud63c\ud55c "
            "\uc790\uc758 \uc77c\ubc29\uc740 "
            "\uc7ac\uc0b0\ubd84\ud560\uc744 "
            "\uccad\uad6c\ud560 \uc218 \uc788\ub2e4."
        ),
        "source": "law_api:001706",
        "law_id": "001706",
        "mst": "284415",
        "law_key": "0017062026031721454",
        "law_name": "\ubbfc\ubc95",
        "law_type": "\ubc95\ub960",
        "ministry": "\ubc95\ubb34\ubd80",
        "effective_date": "20260317",
        "promulgation_date": "20260317",
        "promulgation_number": "21454",
        "article_key": "8390201",
        "article_number": "839",
        "article_branch_number": "2",
        "article_label": "\uc81c839\uc870\uc7582",
        "article_title": (
            "\uc7ac\uc0b0\ubd84\ud560\uccad\uad6c\uad8c"
        ),
        "article_effective_date": "20260317",
    }


def test_statute_collection_name_is_separate():
    assert getattr(
        config,
        "LEGAL_STATUTES_COLLECTION_NAME",
        None,
    ) == "legal_statutes"


def test_vector_store_preserves_statute_metadata(
    tmp_path,
):
    store = ChromaVectorStore(
        persist_directory=tmp_path / "chroma",
        collection_name="legal_statutes",
    )

    document = sample_statute_chunk()

    store.upsert_documents(
        documents=[document],
        embeddings=[[1.0, 0.0]],
    )

    stored = store.collection.get(
        ids=[document["chunk_id"]],
        include=["documents", "metadatas"],
    )

    metadata = stored["metadatas"][0]

    assert metadata["law_id"] == "001706"
    assert metadata["mst"] == "284415"
    assert metadata["law_name"] == "\ubbfc\ubc95"
    assert metadata["effective_date"] == "20260317"
    assert metadata["article_number"] == "839"
    assert metadata["article_branch_number"] == "2"
    assert metadata["article_label"] == (
        "\uc81c839\uc870\uc7582"
    )
    assert metadata["article_title"] == (
        "\uc7ac\uc0b0\ubd84\ud560\uccad\uad6c\uad8c"
    )

    results = store.search(
        query_embedding=[1.0, 0.0],
        top_k=1,
        where={
            "law_id": "001706",
        },
    )

    assert len(results) == 1
    assert results[0]["law_id"] == "001706"
    assert results[0]["law_name"] == "\ubbfc\ubc95"
    assert results[0]["article_number"] == "839"
    assert results[0]["article_label"] == (
        "\uc81c839\uc870\uc7582"
    )
