import json
from urllib.parse import parse_qs, urlparse

import pytest

from rag.precedent_api import PrecedentApiClient


def test_search_precedents_normalizes_page_and_filters():
    calls = []

    def fake_transport(url, timeout):
        calls.append((url, timeout))

        payload = {
            "PrecSearch": {
                "totalCnt": "1",
                "page": "2",
                "prec": {
                    "\ud310\ub840\uc77c\ub828\ubc88\ud638": "300001",
                    "\uc0ac\uac74\uba85": (
                        "\uc7ac\uc0b0\ubd84\ud560 \ub4f1"
                    ),
                    "\uc0ac\uac74\ubc88\ud638": (
                        "2023\ub4dc\ud56912345"
                    ),
                    "\uc120\uace0\uc77c\uc790": (
                        "2024.01.15"
                    ),
                    "\ubc95\uc6d0\uba85": (
                        "\uc11c\uc6b8\uac00\uc815\ubc95\uc6d0"
                    ),
                    "\ubc95\uc6d0\uc885\ub958\ucf54\ub4dc": (
                        "400202"
                    ),
                    "\uc0ac\uac74\uc885\ub958\uba85": (
                        "\uac00\uc0ac"
                    ),
                    "\uc0ac\uac74\uc885\ub958\ucf54\ub4dc": (
                        "400106"
                    ),
                    "\ud310\uacb0\uc720\ud615": (
                        "\ud310\uacb0"
                    ),
                    "\uc120\uace0": "\uc120\uace0",
                    "\ub370\uc774\ud130\ucd9c\ucc98\uba85": (
                        "\ub300\ubc95\uc6d0"
                    ),
                    "\ud310\ub840\uc0c1\uc138\ub9c1\ud06c": (
                        "/DRF/lawService.do"
                        "?target=prec&ID=300001"
                    ),
                },
            }
        }

        return json.dumps(
            payload,
            ensure_ascii=False,
        ).encode("utf-8")

    client = PrecedentApiClient(
        oc="test-oc",
        transport=fake_transport,
    )

    result = client.search_precedents(
        query="\uc7ac\uc0b0\ubd84\ud560",
        search_scope=2,
        display=5,
        page=2,
        court_type_code="400202",
        referenced_law="\ubbfc\ubc95",
        decision_date_from="20160101",
        decision_date_to="20260804",
    )

    assert result.total_count == 1
    assert result.page == 2

    assert result.items == [
        {
            "precedent_id": "300001",
            "case_name": "\uc7ac\uc0b0\ubd84\ud560 \ub4f1",
            "case_number": "2023\ub4dc\ud56912345",
            "decision_date": "20240115",
            "court_name": "\uc11c\uc6b8\uac00\uc815\ubc95\uc6d0",
            "court_type_code": "400202",
            "case_type_name": "\uac00\uc0ac",
            "case_type_code": "400106",
            "decision_type": "\ud310\uacb0",
            "decision": "\uc120\uace0",
            "data_source_name": "\ub300\ubc95\uc6d0",
            "detail_link": (
                "/DRF/lawService.do"
                "?target=prec&ID=300001"
            ),
        }
    ]

    params = parse_qs(
        urlparse(calls[0][0]).query
    )

    assert params["OC"] == ["test-oc"]
    assert params["target"] == ["prec"]
    assert params["type"] == ["JSON"]
    assert params["search"] == ["2"]
    assert params["query"] == [
        "\uc7ac\uc0b0\ubd84\ud560"
    ]
    assert params["display"] == ["5"]
    assert params["page"] == ["2"]
    assert params["org"] == ["400202"]
    assert params["JO"] == ["\ubbfc\ubc95"]
    assert params["prncYd"] == [
        "20160101~20260804"
    ]
    assert params["datSrcNm"] == [
        "\ub300\ubc95\uc6d0"
    ]
    assert params["sort"] == ["ddes"]
    assert calls[0][1] == 30.0


def test_search_precedents_requires_query_or_law():
    client = PrecedentApiClient(
        oc="test-oc",
        transport=lambda _url, _timeout: b"{}",
    )

    with pytest.raises(
        ValueError,
        match="query or referenced_law",
    ):
        client.search_precedents(
            query=" ",
            referenced_law=" ",
        )


def test_search_precedents_rejects_unknown_court_code():
    client = PrecedentApiClient(
        oc="test-oc",
        transport=lambda _url, _timeout: b"{}",
    )

    with pytest.raises(
        ValueError,
        match="court_type_code",
    ):
        client.search_precedents(
            query="\uc774\ud63c",
            court_type_code="999999",
        )


def test_get_precedent_requests_detail_by_id():
    calls = []

    payload = {
        "PrecService": {
            "\ud310\ub840\uc815\ubcf4\uc77c\ub828\ubc88\ud638": (
                "228541"
            ),
            "\uc0ac\uac74\uba85": "\uac15\uc81c\ucd94\ud589",
            "\uc0ac\uac74\ubc88\ud638": "2021\ub3c47821",
            "\uc120\uace0\uc77c\uc790": "20220819",
            "\ubc95\uc6d0\uba85": "\ub300\ubc95\uc6d0",
            "\ud310\uc2dc\uc0ac\ud56d": "\ud310\uc2dc\uc0ac\ud56d",
            "\ud310\uacb0\uc694\uc9c0": "\ud310\uacb0\uc694\uc9c0",
            "\ud310\ub840\ub0b4\uc6a9": "\ud310\ub840\ub0b4\uc6a9",
        }
    }

    def fake_transport(url, timeout):
        calls.append((url, timeout))

        return json.dumps(
            payload,
            ensure_ascii=False,
        ).encode("utf-8")

    client = PrecedentApiClient(
        oc="test-oc",
        transport=fake_transport,
    )

    result = client.get_precedent(
        precedent_id="228541",
    )

    assert result == payload

    params = parse_qs(
        urlparse(calls[0][0]).query
    )

    assert params["OC"] == ["test-oc"]
    assert params["target"] == ["prec"]
    assert params["type"] == ["JSON"]
    assert params["ID"] == ["228541"]
    assert calls[0][1] == 30.0

def test_client_waits_after_configured_request():
    delays = []

    payload = {
        "PrecService": {
            "판례정보일련번호": "300001",
        }
    }

    client = PrecedentApiClient(
        oc="test-oc",
        request_delay_seconds=0.25,
        sleeper=delays.append,
        transport=lambda _url, _timeout: (
            json.dumps(
                payload,
                ensure_ascii=False,
            ).encode("utf-8")
        ),
    )

    result = client.get_precedent(
        precedent_id="300001",
    )

    assert result == payload
    assert delays == [0.25]