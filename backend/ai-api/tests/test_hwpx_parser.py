from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

import pytest

from rag.hwpx_parser import extract_hwpx_text


SECTION_XML_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<hp:sec xmlns:hp="http://www.hancom.co.kr/hwpml/2011/paragraph">
    <hp:p>
        <hp:run>
            <hp:t>{first_text}</hp:t>
        </hp:run>
    </hp:p>
    <hp:p>
        <hp:run>
            <hp:t>{second_text}</hp:t>
        </hp:run>
    </hp:p>
</hp:sec>
"""


def create_fake_hwpx(
    path: Path,
    sections: dict[str, str],
) -> None:
    """
    테스트용 가짜 HWPX 파일을 만든다.

    HWPX는 ZIP 형식이므로 section XML 파일을
    압축파일 내부에 저장한다.
    """
    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with ZipFile(
        path,
        mode="w",
        compression=ZIP_DEFLATED,
    ) as archive:
        for section_name, xml_content in sections.items():
            archive.writestr(
                section_name,
                xml_content,
            )


def test_extract_hwpx_text_reads_paragraphs(
    tmp_path: Path,
) -> None:
    hwpx_path = tmp_path / "sample.hwpx"

    section_xml = SECTION_XML_TEMPLATE.format(
        first_text="양육비를 청구합니다.",
        second_text="상대방이 지급하지 않고 있습니다.",
    )

    create_fake_hwpx(
        path=hwpx_path,
        sections={
            "Contents/section0.xml": section_xml,
        },
    )

    result = extract_hwpx_text(hwpx_path)

    assert "양육비를 청구합니다." in result
    assert "상대방이 지급하지 않고 있습니다." in result
    assert result == (
        "양육비를 청구합니다.\n"
        "상대방이 지급하지 않고 있습니다."
    )


def test_extract_hwpx_text_reads_sections_in_order(
    tmp_path: Path,
) -> None:
    hwpx_path = tmp_path / "multiple_sections.hwpx"

    section_zero = SECTION_XML_TEMPLATE.format(
        first_text="첫 번째 구역",
        second_text="첫 번째 구역의 두 번째 문단",
    )

    section_one = SECTION_XML_TEMPLATE.format(
        first_text="두 번째 구역",
        second_text="두 번째 구역의 두 번째 문단",
    )

    # ZIP 내부 저장 순서를 일부러 거꾸로 만든다.
    create_fake_hwpx(
        path=hwpx_path,
        sections={
            "Contents/section1.xml": section_one,
            "Contents/section0.xml": section_zero,
        },
    )

    result = extract_hwpx_text(hwpx_path)

    assert result.index("첫 번째 구역") < result.index(
        "두 번째 구역"
    )


def test_extract_hwpx_text_rejects_non_zip_file(
    tmp_path: Path,
) -> None:
    invalid_path = tmp_path / "invalid.hwpx"
    invalid_path.write_text(
        "이 파일은 HWPX 압축파일이 아닙니다.",
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError,
        match="올바른 HWPX",
    ):
        extract_hwpx_text(invalid_path)


def test_extract_hwpx_text_rejects_missing_sections(
    tmp_path: Path,
) -> None:
    hwpx_path = tmp_path / "empty.hwpx"

    create_fake_hwpx(
        path=hwpx_path,
        sections={
            "Contents/header.xml": "<header />",
        },
    )

    with pytest.raises(
        ValueError,
        match="section XML",
    ):
        extract_hwpx_text(hwpx_path)