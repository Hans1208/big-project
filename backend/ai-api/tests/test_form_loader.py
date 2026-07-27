import json

from rag.form_loader import load_form_documents


def test_load_form_documents_converts_parsed_json(tmp_path):
    parsed_file = tmp_path / "전체.json"

    source_data = [
        {
            "form_name": "(부를 정하는 소)",
            "main": "가사소송",
            "sub": "가,나,다류 가사소송",
            "tmpltNo": "I001001368",
            "source_file": (
                "서식_hwpx\\가사소송\\"
                "가,나,다류 가사소송\\"
                "(부를 정하는 소).hwpx"
            ),
            "markdown": (
                "부의 결정의 소\n"
                "피고를 사건본인의 부로 정한다."
            ),
            "tables": [],
        }
    ]

    parsed_file.write_text(
        json.dumps(
            source_data,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    documents = load_form_documents(parsed_file)

    assert documents == [
        {
            "document_id": "I001001368",
            "document_type": "legal_form",
            "title": "(부를 정하는 소)",
            "case_type": "가사소송",
            "case_subtype": "가,나,다류 가사소송",
            "content": (
                "부의 결정의 소\n"
                "피고를 사건본인의 부로 정한다."
            ),
            "source": (
                "서식_hwpx\\가사소송\\"
                "가,나,다류 가사소송\\"
                "(부를 정하는 소).hwpx"
            ),
        }
    ]
