import json
from urllib.parse import parse_qs, urlparse

from rag.statute_api import LawApiClient


def test_search_current_laws_normalizes_results():
    calls = []

    def fake_transport(url, timeout):
        calls.append((url, timeout))

        payload = {
            "LawSearch": {
                "resultCode": "00",
                "resultMsg": "success",
                "totalCnt": "1",
                "law": [
                    {
                        "\ubc95\ub839ID": "001706",
                        "\ubc95\ub839\uc77c\ub828\ubc88\ud638": "284415",
                        "\ubc95\ub839\uba85\ud55c\uae00": "\ubbfc\ubc95",
                        "\uc2dc\ud589\uc77c\uc790": "20260317",
                        "\ubc95\ub839\uad6c\ubd84\uba85": "\ubc95\ub960",
                        "\uc18c\uad00\ubd80\ucc98\uba85": "\ubc95\ubb34\ubd80",
                        "\ubc95\ub839\uc0c1\uc138\ub9c1\ud06c": (
                            "/DRF/lawService.do"
                        ),
                    }
                ],
            }
        }

        return json.dumps(
            payload,
            ensure_ascii=False,
        ).encode("utf-8")

    client = LawApiClient(
        oc="test-oc",
        transport=fake_transport,
    )

    results = client.search_current_laws(
        query="\ubbfc\ubc95",
        display=5,
        page=1,
    )

    assert results == [
        {
            "law_id": "001706",
            "mst": "284415",
            "name": "\ubbfc\ubc95",
            "effective_date": "20260317",
            "law_type": "\ubc95\ub960",
            "ministry": "\ubc95\ubb34\ubd80",
            "detail_link": "/DRF/lawService.do",
        }
    ]

    params = parse_qs(
        urlparse(calls[0][0]).query
    )

    assert params["OC"] == ["test-oc"]
    assert params["target"] == ["eflaw"]
    assert params["type"] == ["JSON"]
    assert params["query"] == ["\ubbfc\ubc95"]
    assert params["nw"] == ["3"]
    assert params["display"] == ["5"]
    assert calls[0][1] == 30.0


def test_get_current_law_requests_detail_by_id():
    calls = []

    payload = {
        "\ubc95\ub839": {
            "\uae30\ubcf8\uc815\ubcf4": {
                "\ubc95\ub839ID": "001706",
                "\ubc95\ub839\uba85_\ud55c\uae00": "\ubbfc\ubc95",
            }
        }
    }

    def fake_transport(url, timeout):
        calls.append((url, timeout))

        return json.dumps(
            payload,
            ensure_ascii=False,
        ).encode("utf-8")

    client = LawApiClient(
        oc="test-oc",
        transport=fake_transport,
    )

    result = client.get_current_law(
        law_id="001706"
    )

    assert result == payload

    params = parse_qs(
        urlparse(calls[0][0]).query
    )

    assert params["OC"] == ["test-oc"]
    assert params["target"] == ["eflaw"]
    assert params["type"] == ["JSON"]
    assert params["ID"] == ["001706"]
