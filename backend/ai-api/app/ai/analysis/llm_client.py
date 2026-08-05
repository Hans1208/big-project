"""
LLM 기반 법률상담 구조화 모델 - 신규 Google GenAI SDK (google-genai) 실시간 호출 코드

흐름:
  상담 텍스트 --(few-shot 포함 프롬프트)--> Gemini Structured Outputs (response_schema)
             --(pydantic 파싱/검증)--> AIAnalysisSchema
             --(검증 실패 시 재시도)--> 최종 반환
"""

import json
import os
import re
from copy import deepcopy
from datetime import date
from pathlib import Path
from typing import List, Type

from google import genai
from google.genai import types
from pydantic import BaseModel, ValidationError

from app.schemas.analysis import AIAnalysisSchema
from app.ai.analysis.prompts import build_system_prompt

# parents[2] == app/ (이 파일이 app/ai/analysis/ 아래에 있음)
_DATA_PATH = Path(__file__).resolve().parents[2] / "data" / "few_shot_examples.json"

# 파일 파싱은 1회만. 예시의 상대날짜를 실제 날짜로 바꾸는 일은 호출할 때마다
# 하므로(서버가 며칠 떠 있어도 "오늘"이 따라가야 한다) 원본만 들고 있는다.
_RAW_EXAMPLES = json.loads(_DATA_PATH.read_text(encoding="utf-8"))["examples"]

_client: genai.Client | None = None


def _get_client() -> genai.Client:
    """신규 google-genai Client 인스턴스 싱글톤 관리"""
    global _client
    if _client is None:
        api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError(".env 파일에 GEMINI_API_KEY가 설정되어 있지 않습니다.")
        _client = genai.Client(api_key=api_key)
    return _client


def _prepare_gemini_schema(pydantic_model: Type[BaseModel]) -> dict:
    """
    Gemini API에서 거부하는 'additional_properties', 'title', '$schema' 등의
    비표준 키를 제거하고 $ref 참조를 풀어 Gemini 호환 JSON 스키마 dict를 생성합니다.
    """
    raw_schema = pydantic_model.model_json_schema()
    root_defs = raw_schema.get("$defs", {})

    def resolve_and_clean(node):
        if isinstance(node, dict):
            # $ref 참조가 있는 경우 $defs에서 찾아 인라인으로 해제
            if "$ref" in node:
                ref_key = node["$ref"].split("/")[-1]
                if ref_key in root_defs:
                    resolved = resolve_and_clean(root_defs[ref_key])
                    merged = {k: v for k, v in node.items() if k != "$ref"}
                    merged.update(resolved)
                    return merged

            cleaned = {}
            for k, v in node.items():
                # Gemini API에서 지원하지 않는 스키마 메타 필드 제거
                if k in (
                    "$defs",
                    "additionalProperties",
                    "additional_properties",
                    "title",
                    "$schema",
                    "default",
                ):
                    continue
                cleaned[k] = resolve_and_clean(v)
            return cleaned
        elif isinstance(node, list):
            return [resolve_and_clean(item) for item in node]
        return node

    return resolve_and_clean(raw_schema)


_RELATIVE_DATE_RE = re.compile(r"^\s*약?\s*(\d+)\s*(년|개월|달)\s*전\s*$")


def _resolve_relative_dates(output: dict, today: date) -> dict:
    """few-shot 예시의 날짜를 오늘 기준 실제 날짜로 바꾼다.

    예시 파일은 날짜를 "약 3년 전", "6개월 전"처럼 상대표현 그대로 적어 두었다.
    few-shot은 지시문보다 강한 신호라, 이대로 두면 프롬프트에 날짜 규칙을 아무리
    써도 모델이 예시를 따라 상대표현을 뱉는다. 그런 값은 연·월·일이 없어서
    _extracted_dates가 통째로 버리므로 서식의 날짜칸이 영영 안 채워진다.

    "약 3년 전"은 연도까지만 알 수 있는 값이라 연도만 적는다 — 없는 월·일을
    지어내면 프롬프트에 적은 "모르는 자리를 채우지 말라"는 규칙과 예시가 어긋난다.
    """
    dates = (output.get("extracted_json") or {}).get("날짜")
    if not isinstance(dates, list):
        return output

    for item in dates:
        if not isinstance(item, dict):
            continue
        m = _RELATIVE_DATE_RE.match(str(item.get("값", "")))
        if not m:
            continue
        n, unit = int(m.group(1)), m.group(2)
        if unit == "년":
            item["값"] = str(today.year - n)
        else:
            months = today.year * 12 + (today.month - 1) - n
            item["값"] = f"{months // 12}-{months % 12 + 1:02d}"
    return output


def _load_few_shot_contents(today: date = None) -> List[dict]:
    """few_shot_examples.json -> google-genai contents 대화 배열로 변환"""
    today = today or date.today()
    contents: List[dict] = []
    for ex in _RAW_EXAMPLES:
        contents.append({"role": "user", "parts": [{"text": ex["input"]}]})
        output = _resolve_relative_dates(deepcopy(ex["output"]), today)
        contents.append(
            {
                "role": "model",
                "parts": [{"text": json.dumps(output, ensure_ascii=False)}],
            }
        )
    return contents


_GEMINI_CLEANED_SCHEMA = _prepare_gemini_schema(AIAnalysisSchema)


def build_contents(consultation_text: str) -> List[dict]:
    """few-shot 대화 흐름 뒤에 실제 입력 상담글을 붙여 대화 배열 생성"""
    contents: List[dict] = _load_few_shot_contents()
    contents.append({"role": "user", "parts": [{"text": consultation_text}]})
    return contents


# 기존 기본값이던 gemini-2.5-flash-lite는 신규 사용자에게 더 이상 제공되지 않아
# 호출하면 404가 난다 ("This model ... is no longer available to new users").
# 모델은 언제든 또 내려갈 수 있으니 환경변수로 갈아끼울 수 있게 열어둔다.
FALLBACK_MODEL = "gemini-3.5-flash"


def analyze_consultation(
    consultation_text: str,
    model_name: str | None = None,
    max_retries: int = 2,
) -> AIAnalysisSchema:
    """
    상담 텍스트를 받아 신규 google-genai SDK로 AIAnalysisSchema 구조화 분석을 수행.
    """
    # 환경변수는 import 시점이 아니라 호출 시점에 읽는다.
    # 이 모듈이 load_dotenv()보다 먼저 import될 수 있어서(.env는 ai/config.py가 읽는다),
    # 모듈 상수로 두면 .env의 KLAC_GEMINI_MODEL이 반영되지 않는다.
    model_name = model_name or os.environ.get("KLAC_GEMINI_MODEL") or FALLBACK_MODEL
    client = _get_client()
    contents = build_contents(consultation_text)
    # 프롬프트를 모듈 상수로 굳히면 서버가 며칠 떠 있는 동안 "오늘"이 기동일에
    # 멈춘다. 호출할 때마다 만들어 날짜가 따라가게 한다.
    system_prompt = build_system_prompt()

    last_error: str | None = None
    raw_content: str = ""

    for attempt in range(max_retries + 1):
        if last_error:
            # 검증 실패 시 모델 답변과 피드백을 이어서 전달
            current_contents = contents + [
                {"role": "model", "parts": [{"text": raw_content}]},
                {
                    "role": "user",
                    "parts": [
                        {
                            "text": (
                                f"방금 출력이 Pydantic 스키마 검증에 실패했습니다: {last_error}\n"
                                "반드시 아래 9개 필드를 하나도 빠짐없이 완벽한 JSON으로 출력하세요:\n"
                                "- summary, case_type, case_subtype, urgency_level, eligibility\n"
                                "- extracted_json, missing_info_json, checklist_json, timeline_json"
                            )
                        }
                    ],
                },
            ]
        else:
            current_contents = contents

        # 정제된 Gemini 전용 스키마 전달
        config = types.GenerateContentConfig(
            system_instruction=system_prompt,
            response_mime_type="application/json",
            response_schema=_GEMINI_CLEANED_SCHEMA,
            temperature=0.1,
            # 2048이면 응답이 중간에 잘려 "Invalid JSON: EOF while parsing"으로 검증에 실패한다.
            # gemini 3.x는 내부 추론 토큰도 이 예산에서 함께 쓰기 때문에 여유를 둔다.
            max_output_tokens=8192,
        )

        response = client.models.generate_content(
            model=model_name,
            contents=current_contents,
            config=config,
        )

        raw_content = response.text

        try:
            return AIAnalysisSchema.model_validate_json(raw_content)
        except ValidationError as e:
            last_error = str(e)
            if attempt == max_retries:
                raise

    raise RuntimeError("unreachable")