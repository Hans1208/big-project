"""Generate structured candidate outputs through Gemini without reading .env files."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

from validator import schema_errors


GENERATOR_ID = "gemini_structured_output_v1"
OPENAI_GENERATOR_ID = "openai_structured_output_v1"
REQUIRED_FIELDS = ("summary", "case_type", "case_subtype", "urgency_level", "eligibility", "extracted_json", "missing_info_json", "checklist_json", "timeline_json")
GENERATION_RESPONSE_SCHEMA = {
    "type": "object", "required": list(REQUIRED_FIELDS),
    "properties": {
        "summary": {"type": "string"}, "case_type": {"type": "string"}, "case_subtype": {"type": "string"},
        "urgency_level": {"type": "string", "enum": ["상", "중", "하"]},
        "eligibility": {"type": "string", "enum": ["대상후보", "비대상후보", "확인필요"]},
        "extracted_json": {"type": "object", "required": ["당사자", "금액", "날짜", "사건개요"], "properties": {
            "당사자": {"type": "array", "items": {"type": "object", "required": ["역할", "이름"], "properties": {"역할": {"type": "string"}, "이름": {"type": "string"}}}},
            "금액": {"type": "integer", "nullable": True},
            "날짜": {"type": "array", "items": {"type": "object", "required": ["항목", "값"], "properties": {"항목": {"type": "string"}, "값": {"type": "string"}}}},
            "사건개요": {"type": "string"},
        }},
        "missing_info_json": {"type": "array", "items": {"type": "string"}},
        "checklist_json": {"type": "array", "items": {"type": "object", "required": ["항목", "결과"], "properties": {"항목": {"type": "string"}, "결과": {"type": "string", "enum": ["충족", "미충족", "확인필요"]}}}},
        "timeline_json": {"type": "array", "items": {"type": "object", "required": ["날짜", "내용"], "properties": {"날짜": {"type": "string"}, "내용": {"type": "string"}}}},
    },
}


def build_prompt(transcript: str) -> str:
    fields = ", ".join(REQUIRED_FIELDS)
    return f"""당신은 법률상담 구조화 출력 생성기입니다. 아래 합성 상담 전사본만 근거로 JSON 객체를 작성하세요.
사실을 추가하거나 법률 결론을 확정하지 말고, 불명확한 정보는 '확인필요' 또는 missing_info_json에 넣으세요.
반드시 다음 필드만 포함하세요: {fields}.
case_type과 case_subtype은 반드시 아래 조합 중 하나만 사용하세요.
- 친족: 약혼, 혼인의 성립, 무효, 취소, 협의이혼, 재판상이혼 등, 이혼 및 위자료, 이혼 및 재산분할청구권, 양육비, 면접교섭권, 입양, 파양, 친양자, 친권, 후견인, 부양
- 상속: 상속일반, 상속분, 상속재산분할, 유언, 유류분
- 가사소송: 가사소송일반, 가,나,다류 가사소송, 라,마류 가사비송, 양육비직접지급명령, 이행명령, 과태료와 감치, 기타
- 가족관계등록: 신고, 국적의 취득과 상실, 성본창설과 개명, 가족관계등록창설, 가족관계등록부정정
urgency_level은 반드시 상, 중, 하 중 하나만 사용하세요. eligibility는 반드시 대상후보, 비대상후보, 확인필요 중 하나만 사용하세요.
extracted_json은 정확히 당사자, 금액, 날짜, 사건개요 키를 포함하세요. 당사자 배열의 각 원소는 {{"역할":"...","이름":"..."}}, 날짜 배열의 각 원소는 {{"항목":"...","값":"YYYY-MM-DD 또는 불명확한 원문 표현"}} 형식입니다. 금액은 하나의 정수 원화 금액(예: 20000000) 또는 null만 사용하고, 금액 배열·객체·문자열은 사용하지 마세요. timeline_json 각 원소는 반드시 {{"날짜":"...","내용":"..."}} 형식입니다. checklist_json 각 원소는 {{"항목":"...","결과":"충족 또는 미충족 또는 확인필요"}} 형식입니다.
마크다운·설명문 없이 JSON 객체만 출력하세요.

[상담 전사본]
{transcript}
"""


def normalize_output_shape(output: dict[str, Any]) -> dict[str, Any]:
    """Normalize a known provider formatting drift without adding any facts."""
    missing = output.get("missing_info_json")
    if isinstance(missing, dict):
        flattened: list[Any] = []
        for key, value in missing.items():
            if isinstance(value, list):
                flattened.extend(str(item) for item in value)
            elif value is not None:
                flattened.append(f"{key}: {value}")
        output["missing_info_json"] = flattened
    elif isinstance(missing, list):
        normalized: list[Any] = []
        for item in missing:
            if isinstance(item, dict) and item.get("항목"):
                status = item.get("상태") or item.get("결과")
                normalized.append(f"{item['항목']}: {status}" if status else str(item["항목"]))
            else:
                normalized.append(item)
        output["missing_info_json"] = normalized
    return output


def generate_structured_output(transcript: str, model: str, api_key: str, max_retries: int = 1) -> dict[str, Any]:
    """Call Gemini only with a caller-provided environment key; never load dotenv."""
    try:
        from google import genai
        from google.genai import types
    except ImportError as error:
        raise RuntimeError("google-genai must be installed to generate candidate outputs") from error
    client = genai.Client(api_key=api_key)
    prompt = build_prompt(transcript)
    for attempt in range(max_retries + 1):
        response = client.models.generate_content(
            model=model,
            contents=prompt,
            config=types.GenerateContentConfig(response_mime_type="application/json", response_schema=GENERATION_RESPONSE_SCHEMA, temperature=0.2),
        )
        output = normalize_output_shape(json.loads(response.text))
        errors = schema_errors(output)
        if not errors:
            return output
        if attempt == max_retries:
            raise ValueError("Generated output failed local JSON Schema: " + "; ".join(errors))
        prompt = build_prompt(transcript) + "\n[이전 출력 오류]\n" + "\n".join(errors) + "\n오류를 고쳐 JSON만 다시 출력하세요."
    raise RuntimeError("unreachable")


def generate_openai_structured_output(transcript: str, model: str, api_key: str, max_retries: int = 1) -> dict[str, Any]:
    """Generate JSON with OpenAI, then enforce the project's local JSON Schema."""
    try:
        from openai import OpenAI
    except ImportError as error:
        raise RuntimeError("openai must be installed to generate OpenAI candidate outputs") from error
    client = OpenAI(api_key=api_key)
    prompt = build_prompt(transcript)
    for attempt in range(max_retries + 1):
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "system", "content": "Return only a JSON object."}, {"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.2,
        )
        output = normalize_output_shape(json.loads(response.choices[0].message.content or "{}"))
        errors = schema_errors(output)
        if not errors:
            return output
        if attempt == max_retries:
            raise ValueError("Generated output failed local JSON Schema: " + "; ".join(errors))
        prompt = build_prompt(transcript) + "\n[이전 출력 오류]\n" + "\n".join(errors) + "\n오류를 고쳐 JSON만 다시 출력하세요."
    raise RuntimeError("unreachable")


def write_bundle(case_id: str, output: dict[str, Any], destination: Path, generator_id: str = GENERATOR_ID) -> None:
    bundle = {"case_id": case_id, "answer_generator": generator_id, "ai_output": output, "rag_results": []}
    destination.write_text(json.dumps(bundle, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate independent Gemini candidate outputs for synthetic transcripts.")
    parser.add_argument("--model", required=True, help="Provider model name approved for this project")
    parser.add_argument("--provider", choices=("gemini", "openai"), default="gemini")
    parser.add_argument("--catalog", type=Path, default=Path("data/scenario_catalog.json"))
    parser.add_argument("--output-dir", type=Path, default=Path("data/03_ai_outputs/generated"))
    parser.add_argument("--max-retries", type=int, default=2)
    parser.add_argument("--only-missing", action="store_true", help="Preserve existing generated bundles and call the API only for missing cases.")
    parser.add_argument("--difficulty", choices=("easy", "medium", "hard"), help="Generate one difficulty batch at a time.")
    args = parser.parse_args()
    api_key = (os.environ.get("OPENAI_API_KEY") if args.provider == "openai" else os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY"))
    if not api_key:
        raise SystemExit("Set the selected provider API key in the current process environment; .env is not read.")
    catalog = json.loads(args.catalog.read_text(encoding="utf-8"))
    if args.difficulty:
        catalog = [item for item in catalog if item["difficulty"] == args.difficulty]
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for item in catalog:
        path = args.output_dir / f"{item['case_id']}.json"
        if args.only_missing and path.exists():
            print(f"Skipped existing {path}")
            continue
        transcript = (args.catalog.parent / item["transcript_path"]).read_text(encoding="utf-8")
        output = generate_openai_structured_output(transcript, args.model, api_key, args.max_retries) if args.provider == "openai" else generate_structured_output(transcript, args.model, api_key, args.max_retries)
        write_bundle(item["case_id"], output, path, OPENAI_GENERATOR_ID if args.provider == "openai" else GENERATOR_ID)
        print(f"Created {path}")
