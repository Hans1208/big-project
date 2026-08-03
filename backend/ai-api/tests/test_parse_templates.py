import json
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

import pytest

from rag.parse_templates import (
    load_manifest,
    parse_templates,
    write_parsed_templates,
)


SECTION_XML = """<?xml version="1.0" encoding="UTF-8"?>
<hp:sec xmlns:hp="http://www.hancom.co.kr/hwpml/2011/paragraph">
    <hp:p>
        <hp:run>
            <hp:t>{text}</hp:t>
        </hp:run>
    </hp:p>
</hp:sec>
"""


def create_fake_hwpx(
    path: Path,
    text: str,
) -> None:
    """테스트용 HWPX 압축파일을 생성한다."""
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with ZipFile(
        path,
        mode="w",
        compression=ZIP_DEFLATED,
    ) as archive:
        archive.writestr(
            "Contents/section0.xml",
            SECTION_XML.format(text=text),
        )


def write_manifest(
    path: Path,
    manifest: list[dict],
) -> None:
    """테스트용 manifest JSON을 저장한다."""
    path.write_text(
        json.dumps(
            manifest,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def create_manifest_item(
    template_id: str,
    file_path: str,
) -> dict:
    return {
        "template_id": template_id,
        "template_name": Path(file_path).stem,
        "case_type": "친족",
        "case_subtype": "양육비",
        "file_name": Path(file_path).name,
        "file_path": file_path,
        "file_extension": ".hwpx",
        "parsing_status": "pending",
    }


def test_parse_templates_extracts_hwpx_content(
    tmp_path: Path,
) -> None:
    source_dir = tmp_path / "templates"
    manifest_path = tmp_path / "manifest.json"

    relative_path = (
        "친족/양육비/양육비 심판청구서.hwpx"
    )

    create_fake_hwpx(
        source_dir / relative_path,
        "상대방에게 양육비 지급을 청구합니다.",
    )

    write_manifest(
        manifest_path,
        [
            create_manifest_item(
                template_id="template_001",
                file_path=relative_path,
            )
        ],
    )

    results = parse_templates(
        manifest_path=manifest_path,
        source_dir=source_dir,
    )

    assert len(results) == 1

    result = results[0]

    assert result["template_id"] == "template_001"
    assert result["parsing_status"] == "success"
    assert result["parse_error"] is None
    assert (
        result["content"]
        == "상대방에게 양육비 지급을 청구합니다."
    )
    assert result["char_count"] == len(
        "상대방에게 양육비 지급을 청구합니다."
    )


def test_parse_templates_records_failure_and_continues(
    tmp_path: Path,
) -> None:
    source_dir = tmp_path / "templates"
    manifest_path = tmp_path / "manifest.json"

    valid_path = "친족/양육비/정상서식.hwpx"
    missing_path = "친족/양육비/없는서식.hwpx"

    create_fake_hwpx(
        source_dir / valid_path,
        "정상적으로 추출되는 문서입니다.",
    )

    write_manifest(
        manifest_path,
        [
            create_manifest_item(
                template_id="template_valid",
                file_path=valid_path,
            ),
            create_manifest_item(
                template_id="template_missing",
                file_path=missing_path,
            ),
        ],
    )

    results = parse_templates(
        manifest_path=manifest_path,
        source_dir=source_dir,
    )

    assert len(results) == 2

    result_by_id = {
        result["template_id"]: result
        for result in results
    }

    assert (
        result_by_id["template_valid"][
            "parsing_status"
        ]
        == "success"
    )

    failed_result = result_by_id[
        "template_missing"
    ]

    assert failed_result["parsing_status"] == "failed"
    assert failed_result["content"] == ""
    assert failed_result["char_count"] == 0
    assert "찾을 수 없습니다" in failed_result["parse_error"]


def test_load_manifest_rejects_duplicate_template_ids(
    tmp_path: Path,
) -> None:
    manifest_path = tmp_path / "manifest.json"

    write_manifest(
        manifest_path,
        [
            create_manifest_item(
                template_id="duplicate_id",
                file_path="친족/양육비/첫번째.hwpx",
            ),
            create_manifest_item(
                template_id="duplicate_id",
                file_path="친족/양육비/두번째.hwpx",
            ),
        ],
    )

    with pytest.raises(
        ValueError,
        match="중복된 template_id",
    ):
        load_manifest(manifest_path)


def test_write_parsed_templates_creates_json_file(
    tmp_path: Path,
) -> None:
    output_path = tmp_path / "parsed_templates.json"

    parsed_templates = [
        {
            "template_id": "template_test",
            "template_name": "테스트 서식",
            "case_type": "친족",
            "case_subtype": "양육비",
            "file_name": "테스트 서식.hwpx",
            "file_path": "친족/양육비/테스트 서식.hwpx",
            "file_extension": ".hwpx",
            "content": "테스트 본문",
            "char_count": 6,
            "parsing_status": "success",
            "parse_error": None,
        }
    ]

    write_parsed_templates(
        parsed_templates=parsed_templates,
        output_path=output_path,
    )

    assert output_path.exists()

    saved_data = json.loads(
        output_path.read_text(encoding="utf-8")
    )

    assert saved_data == parsed_templates