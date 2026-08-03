from rag.statute_documents import (
    build_statute_chunks,
)


def test_build_statute_chunks_prepares_embedding_document():
    article = {
        "document_id": "statute:001706:839:2",
        "law_id": "001706",
        "mst": "284415",
        "law_name": "\ubbfc\ubc95",
        "law_type": "\ubc95\ub960",
        "ministry": "\ubc95\ubb34\ubd80",
        "effective_date": "20260317",
        "article_key": "8390201",
        "article_number": "839",
        "article_branch_number": "2",
        "article_label": "\uc81c839\uc870\uc7582",
        "article_title": (
            "\uc7ac\uc0b0\ubd84\ud560\uccad\uad6c\uad8c"
        ),
        "text": (
            "\ubbfc\ubc95 \uc81c839\uc870\uc7582"
            "(\uc7ac\uc0b0\ubd84\ud560\uccad\uad6c\uad8c)\n"
            "\u2460 \ud611\uc758\uc0c1 \uc774\ud63c\ud55c "
            "\uc790\uc758 \uc77c\ubc29\uc740 \ub2e4\ub978 "
            "\uc77c\ubc29\uc5d0 \ub300\ud558\uc5ec "
            "\uc7ac\uc0b0\ubd84\ud560\uc744 "
            "\uccad\uad6c\ud560 \uc218 \uc788\ub2e4."
        ),
        "source": "law_api:001706",
    }

    chunks = build_statute_chunks(
        [article],
        chunk_size=500,
        chunk_overlap=50,
    )

    assert len(chunks) == 1

    chunk = chunks[0]

    assert chunk["document_id"] == (
        "statute:001706:839:2"
    )
    assert chunk["chunk_id"] == (
        "statute:001706:839:2::chunk-0000"
    )
    assert chunk["chunk_index"] == 0
    assert chunk["document_type"] == (
        "legal_statute"
    )
    assert chunk["title"] == (
        "\ubbfc\ubc95 "
        "\uc81c839\uc870\uc7582"
        "(\uc7ac\uc0b0\ubd84\ud560\uccad\uad6c\uad8c)"
    )
    assert chunk["content"] == article["text"]

    assert chunk["law_id"] == "001706"
    assert chunk["mst"] == "284415"
    assert chunk["article_number"] == "839"
    assert chunk["article_branch_number"] == "2"

    assert (
        "\ubc95\ub839\uba85: \ubbfc\ubc95"
        in chunk["embedding_text"]
    )
    assert (
        "\uc870\ubb38: \uc81c839\uc870\uc7582"
        "(\uc7ac\uc0b0\ubd84\ud560\uccad\uad6c\uad8c)"
        in chunk["embedding_text"]
    )
    assert article["text"] in chunk["embedding_text"]
    assert "\uc11c\uc2dd\uba85:" not in (
        chunk["embedding_text"]
    )
