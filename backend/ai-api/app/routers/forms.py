from fastapi import APIRouter, HTTPException

from app.ai.forms.recommender import recommend
from app.ai.forms.drafter import draft, find_hwpx
from app.ai.forms.verifier import verify
from app.ai.forms import monitor

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
    payload 선택 키: applicant_name, opponent_name — 상담원이 화면에서 직접
    확인하고 고친 이름이다. 요약문에서 뽑아낸 이름보다 이쪽이 정확하므로,
    주면 이름칸을 코드가 직접 채운다(drafter.draft 참고).

    반환에 초안 파일 경로(file)와 llm_judge 환각 재검증 결과가 포함된다.
    이 결과는 항상 '검토 대기'로 취급하고, 최종 확정은 상담원/변호사가
    수행해야 한다 (HITL) — 여기서 파일을 자동 확정하지 않는다."""
    form_name = payload.get("form_name")
    if not form_name:
        raise HTTPException(status_code=400, detail="form_name이 필요합니다")
    return draft(form_name, payload.get("extracted", {}), payload.get("summary", ""),
                 payload.get("applicant_name") or "",
                 payload.get("opponent_name") or "")


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


@router.get("/revisions")
def check_form_revisions():
    """helplaw24 서식 목록을 받아 직전 스냅샷과 비교한다 (요구사항 AI-05-04-01).

    신규·개정·삭제·분류변경·이름변경을 찾아서 돌려주기만 한다. 서식 파일을
    자동으로 교체하지 않는다 — 원본이 .hwp라 구조가 바뀐 걸 모른 채 갈아끼우면
    초안 생성이 조용히 어긋난다. 교체는 관리자가 확인하고 직접 넣는다.

    스냅샷은 여기서 갱신하지 않는다. 확인만 여러 번 해도 결과가 같아야 하고,
    관리자가 보기 전에 기준선이 바뀌면 변경 내용이 묻히기 때문이다."""
    try:
        return monitor.check()
    except monitor.FormMonitorError as exc:
        # 수집 실패를 '변경 없음'으로 돌려주면 관리자는 점검이 정상이라고 오해한다.
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post("/revisions/acknowledge")
def acknowledge_form_revisions():
    """관리자가 변경 내용을 확인했다는 표시로 현재 상태를 새 기준선으로 저장한다.

    이걸 눌러야 같은 변경이 다음 점검에서 다시 올라오지 않는다."""
    try:
        return monitor.acknowledge()
    except monitor.FormMonitorError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
