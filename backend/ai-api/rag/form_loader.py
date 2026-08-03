"""파싱한 법률 서식 JSON을 RAG 공통 문서 형식으로 변환한다."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


REQUIRED_FIELDS = (
    "form_name",
    "main",
    "sub",
    "tmpltNo",
    "source_file",
    "markdown",
)


def load_form_documents(
    parsed_file: str | Path,
) -> list[dict[str, str]]:
    """전체.json을 읽어 법률 서식 문서 목록으로 변환한다.

    Args:
        parsed_file:
            parsed/전체.json 경로.

    Returns:
        RAG 파이프라인에서 공통으로 사용하는 문서 목록.

    Raises:
        FileNotFoundError:
            JSON 파일이 존재하지 않을 때.
        ValueError:
            JSON 구조가 잘못됐거나 필수 필드가 없을 때.
    """
    path = Path(parsed_file)

    with path.open(
        "r",
        encoding="utf-8",
    ) as file:
        records: Any = json.load(file)

    if not isinstance(records, list):
        raise ValueError(
            "파싱 결과 JSON의 최상위 구조는 배열이어야 합니다."
        )

    documents: list[dict[str, str]] = []

    for index, record in enumerate(records):
        if not isinstance(record, dict):
            raise ValueError(
                f"{index}번째 서식 데이터가 객체가 아닙니다."
            )

        missing_fields = [
            field
            for field in REQUIRED_FIELDS
            if field not in record
        ]

        if missing_fields:
            missing_text = ", ".join(missing_fields)
            raise ValueError(
                f"{index}번째 서식에 필수 필드가 없습니다: "
                f"{missing_text}"
            )

        content = str(record["markdown"]).strip()

        if not content:
            raise ValueError(
                f"{index}번째 서식의 markdown이 비어 있습니다."
            )

        documents.append(
            {
                "document_id": str(record["tmpltNo"]),
                "document_type": "legal_form",
                "title": str(record["form_name"]),
                "case_type": str(record["main"]),
                "case_subtype": str(record["sub"]),
                "content": content,
                "source": str(record["source_file"]),
            }
        )

    return documents
