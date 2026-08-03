from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any


try:
    from .config import CLASSIFICATION_PATH, DATA_DIR
except ImportError:
    # python rag/build_template_manifest.py 방식으로 실행할 때 사용
    from config import CLASSIFICATION_PATH, DATA_DIR


DEFAULT_OUTPUT_PATH = DATA_DIR / "template_manifest.json"


def load_classification(
    classification_path: Path,
) -> dict[str, list[str]]:
    """사건 대분류·소분류 목록을 JSON 파일에서 읽는다."""
    classification_path = Path(classification_path)

    if not classification_path.exists():
        raise FileNotFoundError(
            "사건 분류 파일을 찾을 수 없습니다: "
            f"{classification_path}"
        )

    with classification_path.open(
        "r",
        encoding="utf-8",
    ) as file:
        classification = json.load(file)

    if not isinstance(classification, dict):
        raise ValueError(
            "사건 분류 파일의 최상위 값은 객체여야 합니다."
        )

    for case_type, subtypes in classification.items():
        if not isinstance(case_type, str):
            raise ValueError(
                "사건 대분류는 문자열이어야 합니다."
            )

        if not isinstance(subtypes, list):
            raise ValueError(
                f"'{case_type}'의 소분류는 배열이어야 합니다."
            )

        if not all(
            isinstance(subtype, str)
            for subtype in subtypes
        ):
            raise ValueError(
                f"'{case_type}'의 모든 소분류는 문자열이어야 합니다."
            )

    return classification


def make_template_id(relative_path: Path) -> str:
    """
    상대경로를 이용해 재실행해도 동일한 서식 ID를 생성한다.

    같은 파일 경로는 항상 같은 template_id를 갖는다.
    """
    normalized_path = (
        relative_path
        .as_posix()
        .strip()
        .lower()
    )

    digest = hashlib.sha256(
        normalized_path.encode("utf-8")
    ).hexdigest()[:12]

    return f"template_{digest}"


def validate_category(
    case_type: str,
    case_subtype: str,
    classification: dict[str, list[str]],
    relative_path: Path,
) -> None:
    """대분류와 소분류가 분류표에 존재하는지 확인한다."""
    valid_subtypes = classification.get(case_type)

    if (
        valid_subtypes is None
        or case_subtype not in valid_subtypes
    ):
        raise ValueError(
            "등록되지 않은 사건 분류입니다. "
            f"대분류='{case_type}', "
            f"소분류='{case_subtype}', "
            f"파일='{relative_path.as_posix()}'"
        )


def build_manifest(
    source_dir: Path,
    classification_path: Path = CLASSIFICATION_PATH,
) -> list[dict[str, Any]]:
    """
    HWPX 폴더를 순회해 서식 manifest를 생성한다.

    기대하는 폴더 구조:
        source_dir/
        └─ 대분류/
           └─ 소분류/
              └─ 서식.hwpx
    """
    source_dir = Path(source_dir).resolve()
    classification_path = Path(classification_path)

    if not source_dir.exists():
        raise FileNotFoundError(
            f"서식 폴더를 찾을 수 없습니다: {source_dir}"
        )

    if not source_dir.is_dir():
        raise NotADirectoryError(
            f"서식 경로가 폴더가 아닙니다: {source_dir}"
        )

    classification = load_classification(
        classification_path
    )

    hwpx_files = sorted(
        (
            path
            for path in source_dir.rglob("*")
            if path.is_file()
            and path.suffix.lower() == ".hwpx"
        ),
        key=lambda path: (
            path.relative_to(source_dir)
            .as_posix()
            .lower()
        ),
    )

    if not hwpx_files:
        raise ValueError(
            f"HWPX 파일이 없습니다: {source_dir}"
        )

    manifest: list[dict[str, Any]] = []

    for file_path in hwpx_files:
        relative_path = file_path.relative_to(
            source_dir
        )

        path_parts = relative_path.parts

        if len(path_parts) < 3:
            raise ValueError(
                "서식 파일은 반드시 "
                "'대분류/소분류/파일명.hwpx' "
                "구조에 있어야 합니다: "
                f"{relative_path.as_posix()}"
            )

        case_type = path_parts[0]
        case_subtype = path_parts[1]

        validate_category(
            case_type=case_type,
            case_subtype=case_subtype,
            classification=classification,
            relative_path=relative_path,
        )

        template = {
            "template_id": make_template_id(
                relative_path
            ),
            "template_name": file_path.stem,
            "case_type": case_type,
            "case_subtype": case_subtype,
            "file_name": file_path.name,
            "file_path": relative_path.as_posix(),
            "file_extension": file_path.suffix.lower(),
            "parsing_status": "pending",
        }

        manifest.append(template)

    return manifest


def write_manifest(
    manifest: list[dict[str, Any]],
    output_path: Path,
) -> None:
    """manifest를 UTF-8 JSON 파일로 저장한다."""
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
            manifest,
            file,
            ensure_ascii=False,
            indent=2,
        )

        file.write("\n")


def print_summary(
    manifest: list[dict[str, Any]],
    output_path: Path,
) -> None:
    """생성 결과를 대분류별로 출력한다."""
    case_type_counts = Counter(
        item["case_type"]
        for item in manifest
    )

    print("\n=== 법률 서식 manifest 생성 완료 ===")
    print(f"전체 서식 수: {len(manifest)}건")

    for case_type in sorted(case_type_counts):
        print(
            f"- {case_type}: "
            f"{case_type_counts[case_type]}건"
        )

    print(f"저장 위치: {Path(output_path).resolve()}")


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "HWPX 법률 서식 폴더를 탐색하여 "
            "template_manifest.json을 생성합니다."
        )
    )

    parser.add_argument(
        "--source-dir",
        required=True,
        help="HWPX 서식 최상위 폴더 경로",
    )

    parser.add_argument(
        "--output",
        default=str(DEFAULT_OUTPUT_PATH),
        help=(
            "manifest 출력 경로 "
            f"(기본값: {DEFAULT_OUTPUT_PATH})"
        ),
    )

    parser.add_argument(
        "--classification",
        default=str(CLASSIFICATION_PATH),
        help=(
            "사건 분류 JSON 경로 "
            f"(기본값: {CLASSIFICATION_PATH})"
        ),
    )

    return parser.parse_args()


def main() -> None:
    args = parse_arguments()

    manifest = build_manifest(
        source_dir=Path(args.source_dir),
        classification_path=Path(
            args.classification
        ),
    )

    output_path = Path(args.output)

    write_manifest(
        manifest=manifest,
        output_path=output_path,
    )

    print_summary(
        manifest=manifest,
        output_path=output_path,
    )


if __name__ == "__main__":
    main()