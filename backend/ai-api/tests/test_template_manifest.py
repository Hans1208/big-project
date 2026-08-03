import json
from pathlib import Path

import pytest

from rag.build_template_manifest import (
    build_manifest,
    write_manifest,
)


def create_fake_hwpx(path: Path) -> None:
    """테스트용 가짜 HWPX 파일을 만든다."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"fake-hwpx-content")


def create_classification_file(path: Path) -> None:
    """테스트용 사건 분류 파일을 만든다."""
    classification = {
        "친족": [
            "양육비",
        ],
        "상속": [
            "유류분",
        ],
    }

    path.write_text(
        json.dumps(
            classification,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def test_build_manifest_extracts_category_and_file_information(
    tmp_path: Path,
) -> None:
    source_dir = tmp_path / "templates"
    classification_path = tmp_path / "classification.json"

    create_fake_hwpx(
        source_dir
        / "친족"
        / "양육비"
        / "양육비 심판청구서.hwpx"
    )
    create_fake_hwpx(
        source_dir
        / "상속"
        / "유류분"
        / "유류분반환청구의 소.hwpx"
    )
    create_classification_file(classification_path)

    manifest = build_manifest(
        source_dir=source_dir,
        classification_path=classification_path,
    )

    assert len(manifest) == 2

    manifest_by_name = {
        item["file_name"]: item
        for item in manifest
    }

    family_template = manifest_by_name[
        "양육비 심판청구서.hwpx"
    ]

    assert family_template["case_type"] == "친족"
    assert family_template["case_subtype"] == "양육비"
    assert family_template["template_name"] == "양육비 심판청구서"
    assert family_template["file_extension"] == ".hwpx"
    assert family_template["parsing_status"] == "pending"
    assert family_template["template_id"].startswith("template_")
    assert (
        family_template["file_path"]
        == "친족/양육비/양육비 심판청구서.hwpx"
    )


def test_build_manifest_rejects_unknown_subtype(
    tmp_path: Path,
) -> None:
    source_dir = tmp_path / "templates"
    classification_path = tmp_path / "classification.json"

    create_fake_hwpx(
        source_dir
        / "친족"
        / "등록되지않은분류"
        / "잘못된서식.hwpx"
    )
    create_classification_file(classification_path)

    with pytest.raises(
        ValueError,
        match="등록되지 않은 사건 분류",
    ):
        build_manifest(
            source_dir=source_dir,
            classification_path=classification_path,
        )


def test_write_manifest_creates_json_file(
    tmp_path: Path,
) -> None:
    output_path = tmp_path / "template_manifest.json"

    manifest = [
        {
            "template_id": "template_test",
            "template_name": "테스트 서식",
            "case_type": "친족",
            "case_subtype": "양육비",
            "file_name": "테스트 서식.hwpx",
            "file_path": "친족/양육비/테스트 서식.hwpx",
            "file_extension": ".hwpx",
            "parsing_status": "pending",
        }
    ]

    write_manifest(
        manifest=manifest,
        output_path=output_path,
    )

    assert output_path.exists()

    saved_data = json.loads(
        output_path.read_text(encoding="utf-8")
    )

    assert saved_data == manifest