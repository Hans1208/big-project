from rag.statute_parser import (
    parse_statute_payload,
)


def test_parse_statute_payload_flattens_article_units():
    payload = {
        "\ubc95\ub839": {
            "\ubc95\ub839\ud0a4": "0017062026031721454",
            "\uae30\ubcf8\uc815\ubcf4": {
                "\ubc95\ub839ID": "001706",
                "\ubc95\ub839\uba85_\ud55c\uae00": "\ubbfc\ubc95",
                "\uc2dc\ud589\uc77c\uc790": "20260317",
                "\uacf5\ud3ec\uc77c\uc790": "20260317",
                "\uacf5\ud3ec\ubc88\ud638": "21454",
                "\ubc95\uc885\uad6c\ubd84": {
                    "content": "\ubc95\ub960",
                    "\ubc95\uc885\uad6c\ubd84\ucf54\ub4dc": "A0002",
                },
                "\uc18c\uad00\ubd80\ucc98": {
                    "content": "\ubc95\ubb34\ubd80",
                    "\uc18c\uad00\ubd80\ucc98\ucf54\ub4dc": "1270000",
                },
            },
            "\uc870\ubb38": {
                "\uc870\ubb38\ub2e8\uc704": [
                    {
                        "\uc870\ubb38\ud0a4": "00170683902",
                        "\uc870\ubb38\ubc88\ud638": "839",
                        "\uc870\ubb38\uac00\uc9c0\ubc88\ud638": "2",
                        "\uc870\ubb38\uc81c\ubaa9": (
                            "\uba74\uc811\uad50\uc12d\uad8c"
                        ),
                        "\uc870\ubb38\uc2dc\ud589\uc77c\uc790": (
                            "20260317"
                        ),
                        "\uc870\ubb38\ub0b4\uc6a9": (
                            "\uc81c839\uc870\uc7582"
                            "(\uba74\uc811\uad50\uc12d\uad8c)"
                        ),
                        "\ud56d": {
                            "\ud56d\ub2e8\uc704": [
                                {
                                    "\ud56d\ubc88\ud638": "1",
                                    "\ud56d\ub0b4\uc6a9": (
                                        "\u2460 \ubd80\ubaa8\uc640 "
                                        "\uc790\ub294 \uc11c\ub85c "
                                        "\uba74\uc811\uad50\uc12d\ud560 "
                                        "\uc218 \uc788\ub2e4."
                                    ),
                                    "\ud638": {
                                        "\ud638\ub2e8\uc704": [
                                            {
                                                "\ud638\ubc88\ud638": "1",
                                                "\ud638\ub0b4\uc6a9": (
                                                    "1. "
                                                    "\uba74\uc811\uc758 "
                                                    "\ubc29\ubc95"
                                                ),
                                                "\ubaa9": {
                                                    "\ubaa9\ub2e8\uc704": [
                                                        {
                                                            "\ubaa9\ubc88\ud638": (
                                                                "\uac00"
                                                            ),
                                                            "\ubaa9\ub0b4\uc6a9": (
                                                                "\uac00. "
                                                                "\ub300\uba74 "
                                                                "\uba74\uc811"
                                                            ),
                                                        }
                                                    ]
                                                },
                                            }
                                        ]
                                    },
                                }
                            ]
                        },
                    }
                ]
            },
        }
    }

    documents = parse_statute_payload(
        payload,
        mst="284415",
    )

    assert len(documents) == 1

    document = documents[0]

    assert document["document_id"] == (
        "statute:001706:839:2"
    )
    assert document["law_id"] == "001706"
    assert document["mst"] == "284415"
    assert document["law_name"] == "\ubbfc\ubc95"
    assert document["law_type"] == "\ubc95\ub960"
    assert document["ministry"] == "\ubc95\ubb34\ubd80"
    assert document["effective_date"] == "20260317"
    assert document["article_number"] == "839"
    assert document["article_branch_number"] == "2"
    assert document["article_label"] == (
        "\uc81c839\uc870\uc7582"
    )
    assert document["article_title"] == (
        "\uba74\uc811\uad50\uc12d\uad8c"
    )

    assert "\uc81c839\uc870\uc7582" in document["text"]
    assert "\u2460 \ubd80\ubaa8\uc640 \uc790\ub294" in document["text"]
    assert "1. \uba74\uc811\uc758 \ubc29\ubc95" in document["text"]
    assert "\uac00. \ub300\uba74 \uba74\uc811" in document["text"]
