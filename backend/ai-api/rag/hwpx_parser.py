from __future__ import annotations

import argparse
import re
import xml.etree.ElementTree as ElementTree
from pathlib import Path
from zipfile import BadZipFile, ZipFile, is_zipfile


SECTION_PATTERN = re.compile(
    r"^Contents/section(\d+)\.xml$",
    re.IGNORECASE,
)


def get_local_name(tag: str) -> str:
    """
    XML namespace를 제외한 태그 이름만 반환한다.

    예:
        {namespace}p -> p
        {namespace}t -> t
    """
    if "}" in tag:
        return tag.rsplit("}", 1)[1]

    if ":" in tag:
        return tag.rsplit(":", 1)[1]

    return tag


def normalize_text(text: str) -> str:
    """
    문서 텍스트의 불필요한 공백을 정리한다.

    문단과 명시적 줄바꿈은 유지하고,
    연속된 일반 공백과 탭은 한 칸으로 줄인다.
    """
    text = text.replace("\u00a0", " ")

    normalized_lines: list[str] = []

    for line in text.splitlines():
        normalized_line = re.sub(
            r"[ \t\r\f\v]+",
            " ",
            line,
        ).strip()

        if normalized_line:
            normalized_lines.append(
                normalized_line
            )

    return "\n".join(normalized_lines)


def extract_paragraph_text(
    paragraph: ElementTree.Element,
) -> str:
    """
    하나의 문단 요소에서 텍스트를 추출한다.

    표 내부처럼 문단 안에 다른 문단이 들어 있는 경우
    중복 추출을 막기 위해 하위 문단은 건너뛴다.
    하위 문단은 전체 XML 순회 과정에서 별도로 추출된다.
    """
    text_parts: list[str] = []

    def walk(element: ElementTree.Element) -> None:
        for child in element:
            child_name = get_local_name(
                child.tag
            )

            if child_name == "p":
                # 중첩 문단은 별도로 처리한다.
                continue

            if child_name == "t":
                if child.text:
                    text_parts.append(
                        child.text
                    )
                continue

            if child_name in {
                "lineBreak",
                "br",
            }:
                text_parts.append("\n")
                continue

            if child_name == "tab":
                text_parts.append("\t")
                continue

            walk(child)

    walk(paragraph)

    return normalize_text(
        "".join(text_parts)
    )


def extract_section_text(
    xml_content: bytes,
    section_name: str,
) -> str:
    """하나의 section XML에서 문단 텍스트를 추출한다."""
    try:
        root = ElementTree.fromstring(
            xml_content
        )
    except ElementTree.ParseError as error:
        raise ValueError(
            f"section XML을 해석할 수 없습니다: "
            f"{section_name}"
        ) from error

    paragraphs: list[str] = []

    for element in root.iter():
        if get_local_name(element.tag) != "p":
            continue

        paragraph_text = extract_paragraph_text(
            element
        )

        if paragraph_text:
            paragraphs.append(
                paragraph_text
            )

    return "\n".join(paragraphs)


def get_section_names(
    archive: ZipFile,
) -> list[str]:
    """
    ZIP 내부에서 Contents/sectionN.xml 파일을 찾아
    section 번호 순서대로 반환한다.
    """
    section_names: list[
        tuple[int, str]
    ] = []

    for file_name in archive.namelist():
        normalized_name = file_name.replace(
            "\\",
            "/",
        )

        match = SECTION_PATTERN.match(
            normalized_name
        )

        if match is None:
            continue

        section_number = int(
            match.group(1)
        )

        section_names.append(
            (
                section_number,
                file_name,
            )
        )

    section_names.sort(
        key=lambda item: item[0]
    )

    return [
        file_name
        for _, file_name in section_names
    ]


def extract_hwpx_text(
    hwpx_path: str | Path,
) -> str:
    """
    HWPX 파일의 모든 section XML에서 본문을 추출한다.
    """
    hwpx_path = Path(hwpx_path)

    if not hwpx_path.exists():
        raise FileNotFoundError(
            f"HWPX 파일을 찾을 수 없습니다: "
            f"{hwpx_path}"
        )

    if not hwpx_path.is_file():
        raise ValueError(
            f"HWPX 경로가 파일이 아닙니다: "
            f"{hwpx_path}"
        )

    if not is_zipfile(hwpx_path):
        raise ValueError(
            "올바른 HWPX 압축파일이 아닙니다: "
            f"{hwpx_path}"
        )

    section_texts: list[str] = []

    try:
        with ZipFile(
            hwpx_path,
            mode="r",
        ) as archive:
            section_names = get_section_names(
                archive
            )

            if not section_names:
                raise ValueError(
                    "HWPX 내부에서 section XML을 "
                    f"찾을 수 없습니다: {hwpx_path}"
                )

            for section_name in section_names:
                xml_content = archive.read(
                    section_name
                )

                section_text = extract_section_text(
                    xml_content=xml_content,
                    section_name=section_name,
                )

                if section_text:
                    section_texts.append(
                        section_text
                    )

    except BadZipFile as error:
        raise ValueError(
            "올바른 HWPX 압축파일이 아닙니다: "
            f"{hwpx_path}"
        ) from error

    full_text = "\n\n".join(
        section_texts
    ).strip()

    if not full_text:
        raise ValueError(
            "HWPX 파일에서 본문 텍스트를 "
            f"추출하지 못했습니다: {hwpx_path}"
        )

    return full_text


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "HWPX 법률 서식에서 "
            "본문 텍스트를 추출합니다."
        )
    )

    parser.add_argument(
        "--file",
        required=True,
        help="텍스트를 추출할 HWPX 파일 경로",
    )

    parser.add_argument(
        "--preview-chars",
        type=int,
        default=2000,
        help="터미널에 출력할 최대 글자 수",
    )

    return parser.parse_args()


def main() -> None:
    args = parse_arguments()

    if args.preview_chars <= 0:
        raise ValueError(
            "--preview-chars 값은 "
            "1 이상이어야 합니다."
        )

    extracted_text = extract_hwpx_text(
        args.file
    )

    print("\n=== HWPX 텍스트 추출 완료 ===")
    print(f"파일: {Path(args.file).name}")
    print(f"전체 글자 수: {len(extracted_text)}자")
    print("\n=== 추출 결과 미리보기 ===")

    preview = extracted_text[
        : args.preview_chars
    ]

    print(preview)

    if len(extracted_text) > args.preview_chars:
        print("\n... 이하 생략 ...")


if __name__ == "__main__":
    main()