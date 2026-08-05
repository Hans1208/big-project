import pytest

from rag.precedent_parser import (
    PrecedentParseError,
    parse_precedent_payload,
)


def test_parse_precedent_payload_normalizes_fields():
    payload = {
        "PrecService": {
            "판례정보일련번호": " 300001 ",
            "사건명": "재산분할 등",
            "사건번호": "2023드합12345",
            "선고일자": "2024.01.15",
            "선고": "선고",
            "법원명": "서울가정법원",
            "법원종류코드": "400202",
            "사건종류명": "가사",
            "사건종류코드": "400106",
            "판결유형": "판결",
            "판시사항": (
                "<p>재산분할 대상의 판단</p>"
                "<br/>기준시점"
            ),
            "판결요지": "판결 &amp; 요지",
            "참조조문": "민법 제839조의2",
            "참조판례": "대법원 2020므0000",
            "판례내용": (
                "<div>원심판결 이유</div>"
                "상고를 기각한다."
            ),
        }
    }

    result = parse_precedent_payload(
        payload,
        matched_searches=[
            "keyword:body:재산분할:lower",
            "keyword:title:재산분할:lower",
            "keyword:body:재산분할:lower",
        ],
    )

    assert result == {
        "precedent_id": "300001",
        "case_name": "재산분할 등",
        "case_number": "2023드합12345",
        "decision_date": "20240115",
        "decision": "선고",
        "court_name": "서울가정법원",
        "court_type_code": "400202",
        "court_level": "LOWER",
        "case_type_name": "가사",
        "case_type_code": "400106",
        "decision_type": "판결",
        "holding": (
            "재산분할 대상의 판단\n기준시점"
        ),
        "summary": "판결 & 요지",
        "referenced_statutes": (
            "민법 제839조의2"
        ),
        "referenced_precedents": (
            "대법원 2020므0000"
        ),
        "full_text": (
            "원심판결 이유\n상고를 기각한다."
        ),
        "matched_searches": [
            "keyword:body:재산분할:lower",
            "keyword:title:재산분할:lower",
        ],
        "source": "law_api:prec:300001",
    }


def test_parse_precedent_payload_uses_list_fallback():
    payload = {
        "PrecService": {
            "판례정보일련번호": "300002",
            "사건명": "이혼",
            "판례내용": "판례 본문",
        }
    }

    result = parse_precedent_payload(
        payload,
        list_item={
            "case_number": "2024므1234",
            "court_name": "대법원",
            "court_type_code": "400201",
            "decision_date": "20250102",
            "case_type_name": "가사",
        },
    )

    assert result["case_number"] == "2024므1234"
    assert result["court_name"] == "대법원"
    assert result["court_level"] == "SUPREME"
    assert result["decision_date"] == "20250102"


def test_parse_precedent_payload_rejects_missing_root():
    with pytest.raises(
        PrecedentParseError,
        match="PrecService",
    ):
        parse_precedent_payload({})


def test_parse_precedent_payload_rejects_empty_text():
    with pytest.raises(
        PrecedentParseError,
        match="searchable text",
    ):
        parse_precedent_payload(
            {
                "PrecService": {
                    "판례정보일련번호": "300003",
                    "사건명": "이혼",
                }
            }
        )