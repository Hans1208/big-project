from fastapi import APIRouter

from app.ai.consult.graph import run_consult_analysis
from app.ai.consult.schemas import ConsultAnalyzeResponse, RawInput

router = APIRouter(prefix="/consult", tags=["consult"])


@router.post("/analyze", response_model=ConsultAnalyzeResponse)
async def analyze_consult(payload: RawInput) -> dict:
    """버튼 클릭 1번 = 이 엔드포인트 1회 호출.

    기존에 프론트/Spring이 순서대로 호출하던 3개 엔드포인트
    (/case-analysis -> /eligibility/analyze -> /missing-data/analyze)를
    app.ai.consult 그래프 하나로 통합해, 텍스트+첨부파일을 받아
    사건분석/구조검토 체크리스트/누락자료를 한 번에 반환한다.

    HITL은 이 API 자체의 흐름을 바꾸지 않는다 — 응답은 항상 "검토 대기" 상태로
    프론트/DB에 저장되어야 하며, 상담원/변호사/공익법무관의 최종 확정 액션을 거쳐야 함.
    """
    return await run_consult_analysis({"content": payload.content.model_dump()})
