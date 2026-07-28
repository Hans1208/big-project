import json
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import ValidationError

from app.services.llm_client import analyze_consultation

router = APIRouter(prefix="/analysis", tags=["analysis"])

_CONTRACT = Path(__file__).parents[4] / "contracts" / "ai_analysis_mock.json"
SAMPLE = json.loads(_CONTRACT.read_text(encoding="utf-8"))


@router.get("/{consultation_id}")
def get_analysis(consultation_id: str):
    # 조회는 DB 저장(core-api) 이후에나 실제 데이터를 낼 수 있어 여전히 mock.
    return {**SAMPLE, "consultation_id": consultation_id}


@router.post("")
def create_analysis(payload: dict):
    """상담 텍스트 -> AI_ANALYSIS 구조화 분석 (Gemini, app/services/llm_client.py).

    payload: {"content": {"summary": "...", "details": "..."}} 또는
    {"summary": "...", "details": "..."} 둘 다 받는다."""
    content = payload.get("content", payload)
    text = f"[상담 요약]\n{content.get('summary', '')}\n\n[상세 내용]\n{content.get('details', '')}"

    try:
        result = analyze_consultation(text)
    except ValidationError as e:
        raise HTTPException(status_code=502, detail=f"AI_ANALYSIS 스키마 검증 실패: {e}")

    return result.model_dump()