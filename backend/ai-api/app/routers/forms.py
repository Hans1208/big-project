from fastapi import APIRouter, HTTPException

from app.ai.forms.recommender import recommend
from app.ai.forms.drafter import draft, find_hwpx
from app.ai.forms.verifier import verify

router = APIRouter(prefix="/forms", tags=["forms"])


@router.post("/recommend")
def recommend_forms(payload: dict):
    """analysis(AI_ANALYSIS 형태) → 추천 서식 목록 + 근거.

    payload 필수 키: case_type, case_subtype, summary, extracted_json
    서식 선택은 상담원이 결정한다 (HITL) — 여기선 후보와 근거만 제시."""
    return recommend(payload)


@router.post("/draft")
def draft_form(payload: dict):
    """서식명 + 추출정보 → 초안 HWPX 생성.

    payload 필수 키: form_name, extracted, summary(선택)
    반환에 초안 파일 경로(file)와 llm_judge 환각 재검증 결과가 포함된다.
    이 결과는 항상 '검토 대기'로 취급하고, 최종 확정은 상담원/변호사가
    수행해야 한다 (HITL) — 여기서 파일을 자동 확정하지 않는다."""
    form_name = payload.get("form_name")
    if not form_name:
        raise HTTPException(status_code=400, detail="form_name이 필요합니다")
    return draft(form_name, payload.get("extracted", {}), payload.get("summary", ""))


@router.post("/verify")
def verify_draft(payload: dict):
    """생성된 초안이 추출정보를 제대로 반영했는지 채점(완전/부분/불가).

    payload 필수 키: form_name(원본 서식 조회용), draft_file(draft()가
    반환한 file 경로), extracted"""
    form_name = payload.get("form_name")
    draft_file = payload.get("draft_file")
    if not form_name or not draft_file:
        raise HTTPException(status_code=400, detail="form_name, draft_file이 필요합니다")

    original = find_hwpx(form_name)
    if original is None:
        raise HTTPException(status_code=404, detail=f"서식 파일 없음: {form_name}")

    return verify(str(original), draft_file, payload.get("extracted", {}))
