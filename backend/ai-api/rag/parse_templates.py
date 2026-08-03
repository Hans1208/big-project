from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any


try:
    from .config import (
        PARSED_TEMPLATES_PATH,
        TEMPLATE_MANIFEST_PATH,
    )
    from .hwpx_parser import extract_hwpx_text
except ImportError:
    from config import (
        PARSED_TEMPLATES_PATH,
        TEMPLATE_MANIFEST_PATH,
    )
    from hwpx_parser import extract_hwpx_text


REQUIRED_MANIFEST_FIELDS = {
    "template_id",
    "template_name",
    "case_type",
    "case_subtype",
    "file_name",
    "file_path",
    "file_extension",
}


def load_manifest(
    manifest_path: str | Path,
) -> list[dict[str, Any]]:
    """template_manifest.json을 읽고 구조를 검증한다."""
    manifest_path = Path(manifest_path)

    if not manifest_path.exists():
        raise FileNotFoundError(
            "서식 manifest 파일을 찾을 수 없습니다: "
            f"{manifest_path}"
        )

    with manifest_path.open(
        "r",
        encoding="utf-8",
    ) as file:
        manifest = json.load(file)

    if not isinstance(manifest, list):
        raise ValueError(
            "서식 manifest의 최상위 값은 배열이어야 합니다."
        )

    template_ids: set[str] = set()

    for index, item in enumerate(manifest):
        if not isinstance(item, dict):
            raise ValueError(
                f"manifest의 {index}번째 항목은 "
                "객체여야 합니다."
            )

        missing_fields = (
            REQUIRED_MANIFEST_FIELDS
            - set(item.keys())
        )

        if missing_fields:
            missing_text = ", ".join(
                sorted(missing_fields)
            )

            raise ValueError(
                f"manifest의 {index}번째 항목에 "
                f"필수 필드가 없습니다: {missing_text}"
            )

        template_id = item["template_id"]

        if not isinstance(template_id, str):
            raise ValueError(
                "template_id는 문자열이어야 합니다."
            )

        if template_id in template_ids:
            raise ValueError(
                "중복된 template_id가 존재합니다: "
                f"{template_id}"
            )

        template_ids.add(template_id)

    return manifest


def build_base_result(
    manifest_item: dict[str, Any],
) -> dict[str, Any]:
    """manifest 항목에서 파싱 결과의 기본 구조를 만든다."""
    return {
        "template_id": manifest_item["template_id"],
        "template_name": manifest_item["template_name"],
        "case_type": manifest_item["case_type"],
        "case_subtype": manifest_item["case_subtype"],
        "file_name": manifest_item["file_name"],
        "file_path": manifest_item["file_path"],
        "file_extension": manifest_item[
            "file_extension"
        ],
        "content": "",
        "char_count": 0,
        "parsing_status": "failed",
        "parse_error": None,
    }


def resolve_template_path(
    source_dir: Path,
    relative_file_path: str,
) -> Path:
    """
    manifest의 상대경로를 실제 파일 경로로 변환한다.

    ../ 등의 경로를 이용해 source_dir 외부 파일에
    접근하는 것을 방지한다.
    """
    source_root = source_dir.resolve()

    template_path = (
        source_root
        / Path(relative_file_path)
    ).resolve()

    try:
        template_path.relative_to(source_root)
    except ValueError as error:
        raise ValueError(
            "서식 파일 경로가 원본 폴더 외부를 "
            f"가리킵니다: {relative_file_path}"
        ) from error

    return template_path


def parse_template_item(
    manifest_item: dict[str, Any],
    source_dir: Path,
) -> dict[str, Any]:
    """manifest 항목 하나에 해당하는 HWPX를 파싱한다."""
    result = build_base_result(
        manifest_item
    )

    try:
        template_path = resolve_template_path(
            source_dir=source_dir,
            relative_file_path=manifest_item[
                "file_path"
            ],
        )

        content = extract_hwpx_text(
            template_path
        )

        result["content"] = content
        result["char_count"] = len(content)
        result["parsing_status"] = "success"
        result["parse_error"] = None

    except (
        FileNotFoundError,
        NotADirectoryError,
        OSError,
        ValueError,
    ) as error:
        result["parsing_status"] = "failed"
        result["parse_error"] = str(error)

    return result


def parse_templates(
    manifest_path: str | Path,
    source_dir: str | Path,
) -> list[dict[str, Any]]:
    """manifest의 모든 HWPX 파일을 순서대로 파싱한다."""
    source_dir = Path(source_dir)

    if not source_dir.exists():
        raise FileNotFoundError(
            "HWPX 원본 폴더를 찾을 수 없습니다: "
            f"{source_dir}"
        )

    if not source_dir.is_dir():
        raise NotADirectoryError(
            "HWPX 원본 경로가 폴더가 아닙니다: "
            f"{source_dir}"
        )

    manifest = load_manifest(
        manifest_path
    )

    parsed_templates: list[
        dict[str, Any]
    ] = []

    for manifest_item in manifest:
        parsed_result = parse_template_item(
            manifest_item=manifest_item,
            source_dir=source_dir,
        )

        parsed_templates.append(
            parsed_result
        )

    return parsed_templates


def write_parsed_templates(
    parsed_templates: list[dict[str, Any]],
    output_path: str | Path,
) -> None:
    """일괄 파싱 결과를 UTF-8 JSON으로 저장한다."""
    output_path = Path(output_path)

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with output_path.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            parsed_templates,
            file,
            ensure_ascii=False,
            indent=2,
        )

        file.write("\n")


def print_summary(
    parsed_templates: list[dict[str, Any]],
    output_path: Path,
) -> None:
    """일괄 파싱 결과 요약을 출력한다."""
    status_counts = Counter(
        template["parsing_status"]
        for template in parsed_templates
    )

    success_count = status_counts.get(
        "success",
        0,
    )
    failed_count = status_counts.get(
        "failed",
        0,
    )

    print("\n=== HWPX 일괄 파싱 완료 ===")
    print(f"전체 서식 수: {len(parsed_templates)}건")
    print(f"파싱 성공: {success_count}건")
    print(f"파싱 실패: {failed_count}건")
    print(f"저장 위치: {output_path.resolve()}")

    if failed_count:
        print("\n=== 파싱 실패 목록 ===")

        for template in parsed_templates:
            if (
                template["parsing_status"]
                != "failed"
            ):
                continue

            print(
                f"- {template['file_path']}: "
                f"{template['parse_error']}"
            )


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "template_manifest.json을 기준으로 "
            "모든 HWPX 서식의 본문을 추출합니다."
        )
    )

    parser.add_argument(
        "--source-dir",
        required=True,
        help="HWPX 서식 최상위 폴더 경로",
    )

    parser.add_argument(
        "--manifest",
        default=str(TEMPLATE_MANIFEST_PATH),
        help=(
            "template manifest JSON 경로 "
            f"(기본값: {TEMPLATE_MANIFEST_PATH})"
        ),
    )

    parser.add_argument(
        "--output",
        default=str(PARSED_TEMPLATES_PATH),
        help=(
            "파싱 결과 JSON 경로 "
            f"(기본값: {PARSED_TEMPLATES_PATH})"
        ),
    )

    return parser.parse_args()


def main() -> None:
    args = parse_arguments()

    output_path = Path(args.output)

    parsed_templates = parse_templates(
        manifest_path=Path(args.manifest),
        source_dir=Path(args.source_dir),
    )

    write_parsed_templates(
        parsed_templates=parsed_templates,
        output_path=output_path,
    )

    print_summary(
        parsed_templates=parsed_templates,
        output_path=output_path,
    )


if __name__ == "__main__":
    main()