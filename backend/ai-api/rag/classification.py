import json
from pathlib import Path
from typing import Optional


BASE_DIR = Path(__file__).resolve().parent
CLASSIFICATION_PATH = BASE_DIR / "data" / "case_classification.json"


def load_case_classification() -> dict[str, list[str]]:
    """대분류 및 소분류 체계를 JSON 파일에서 읽는다."""
    if not CLASSIFICATION_PATH.exists():
        raise FileNotFoundError(
            f"사건 분류 파일을 찾을 수 없습니다: {CLASSIFICATION_PATH}"
        )

    with CLASSIFICATION_PATH.open("r", encoding="utf-8") as file:
        classification = json.load(file)

    if not isinstance(classification, dict):
        raise ValueError("사건 분류 데이터는 JSON 객체 형식이어야 합니다.")

    return classification


def validate_case_classification(
    case_type: str,
    case_subtype: str,
    classification: Optional[dict[str, list[str]]] = None,
) -> None:
    """대분류와 소분류의 조합이 올바른지 검사한다."""
    case_type = case_type.strip()
    case_subtype = case_subtype.strip()

    if classification is None:
        classification = load_case_classification()

    if case_type not in classification:
        raise ValueError(f"등록되지 않은 사건 대분류입니다: {case_type}")

    allowed_subtypes = classification[case_type]

    if case_subtype not in allowed_subtypes:
        raise ValueError(
            f"'{case_subtype}'은(는) '{case_type}'의 소분류가 아닙니다. "
            f"사용 가능한 소분류: {', '.join(allowed_subtypes)}"
        )


def build_where_filter(
    case_type: Optional[str] = None,
    case_subtype: Optional[str] = None,
) -> Optional[dict]:
    """ChromaDB 검색용 메타데이터 필터를 만든다."""
    case_type = case_type.strip() if case_type else None
    case_subtype = case_subtype.strip() if case_subtype else None

    if case_subtype and not case_type:
        raise ValueError("소분류를 사용하려면 대분류도 입력해야 합니다.")

    if case_type and case_subtype:
        validate_case_classification(case_type, case_subtype)

        return {
            "$and": [
                {"case_type": {"$eq": case_type}},
                {"case_subtype": {"$eq": case_subtype}},
            ]
        }

    if case_type:
        classification = load_case_classification()

        if case_type not in classification:
            raise ValueError(f"등록되지 않은 사건 대분류입니다: {case_type}")

        return {"case_type": {"$eq": case_type}}

    return None