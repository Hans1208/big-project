from fastapi import APIRouter

from app.ai.analysis import service as analysis_service
from app.ai.consult.graph import run_consult_analysis
from app.ai.consult.schemas import ConsultAnalyzeResponse, RawInput
from app.ai.stt import extract as stt_extract
from app.ai.statutes.service import (
    find_related_statutes,
)

router = APIRouter(prefix="/consult", tags=["consult"])


@router.post("/analyze", response_model=ConsultAnalyzeResponse)
async def analyze_consult(payload: RawInput) -> dict:
    """버튼 클릭 1번 = 이 엔드포인트 1회 호출.

    파이프라인 층을 순서대로 부르고 결과를 합쳐서 돌려준다.

        stt       첨부파일(S3) -> 텍스트
        analysis  텍스트 -> AI_ANALYSIS (요약·세부유형·추출정보·타임라인)
        consult   판정 (사건유형·긴급도·구조대상·체크리스트·누락자료)

    analysis가 파이프라인의 허브다. consult(판정)뿐 아니라 forms(서식 추천·초안)와
    앞으로 붙을 RAG도 서로를 모른 채 각자 이 결과를 읽는다. 그래서 여기서 층을
    나눠 부르고, 각 층은 자기 앞 단계의 출력만 입력으로 받는다.

    HITL은 이 API의 흐름을 바꾸지 않는다 — 응답은 항상 "검토 대기" 상태로
    프론트/DB에 저장되어야 하며, 상담원/변호사/공익법무관의 최종 확정을 거쳐야 함.
    """
    content = payload.content.model_dump()

    # 1) stt — 첨부파일을 텍스트로. 파일을 다루는 건 이 층뿐이다.
    file_links = stt_extract.normalize_file_links(content.get("summited_file_link"))
    extracted = stt_extract.extract_all(file_links)

    # 2) analysis — 상담원 입력 + 첨부 텍스트를 합쳐 AI_ANALYSIS 형태로 구조화
    consult_text = analysis_service.build_consult_text(
        content.get("summary", ""), content.get("details", ""), extracted.text
    )
    analysis = analysis_service.analyze(consult_text)

    # 3) statutes ? ???? ?? ?? ??? ?? ????? ??
    related_statutes = find_related_statutes(
        analysis=analysis,
        fallback_text=consult_text,
        top_n=5,
    )

    # 3) consult — 위 결과와 텍스트를 받아 판정. 이 그래프는 S3/파일을 모른다.
    result = await run_consult_analysis({
        "content": content,
        "extracted": {
            "texts": extracted.texts,
            "details": extracted.details,
            "text": extracted.text,
        },
    })

    return {
        **result,
        **analysis.to_dict(),
        "related_statutes": related_statutes,
    }
