from fastapi import APIRouter

from app.ai.analysis import service as analysis_service
from app.ai.consult.graph import run_consult_analysis
from app.ai.output_validation.service import validate_consultation_output
from app.ai.consult.rag_service import (
    collect_related_legal_sources,
)
from app.ai.consult.schemas import (
    ConsultAnalyzeResponse,
    RawInput,
)
from app.ai.stt import extract as stt_extract


router = APIRouter(
    prefix="/consult",
    tags=["consult"],
)


@router.post(
    "/analyze",
    response_model=ConsultAnalyzeResponse,
)
async def analyze_consult(
    payload: RawInput,
) -> dict:
    """Run the consultation analysis pipeline once."""
    content = payload.content.model_dump()

    # 1) Extract text from attached files.
    file_links = (
        stt_extract.normalize_file_links(
            content.get(
                "summited_file_link"
            )
        )
    )
    extracted = stt_extract.extract_all(
        file_links
    )

    # 2) Existing analysis and consult graphs may use raw
    # consultation text according to their existing contract.
    consult_text = (
        analysis_service.build_consult_text(
            content.get("summary", ""),
            content.get("details", ""),
            extracted.text,
        )
    )
    analysis = analysis_service.analyze(
        consult_text
    )

    # 판정 계층도 같은 원문을 본다. 주민등록번호·전화번호는 여기서도 지운다 -
    # 구조대상 판단과 누락자료 목록에 번호가 실려 나갈 이유가 없고, 실측에서
    # 분석 요약에 지어낸 주민번호가 찍힌 적이 있다(analysis/service.py 주석 참고).
    scrub = analysis_service.scrub_sensitive_numbers
    safe_content = {
        **content,
        "summary": scrub(content.get("summary", "")),
        "details": scrub(content.get("details", "")),
    }
    result = await run_consult_analysis(
        {
            "content": safe_content,
            "extracted": {
                # texts/text는 첨부에서 뽑은 본문이라 지운다.
                # details는 파일별 처리 상태(파일명·성공여부)라 본문이 없다.
                "texts": [scrub(t) for t in (extracted.texts or [])],
                "details": extracted.details,
                "text": scrub(extracted.text or ""),
            },
        }
    )

    # 3) RAG has a stricter privacy boundary.
    # It reads only content.anonymized_text and never
    # falls back to summary, details, or attachment text.
    legal_sources = (
        collect_related_legal_sources(
            content=content,
            top_n=5,
        )
    )
    output_validation = validate_consultation_output(analysis_output=analysis.output, legal_sources=legal_sources)

    return {
        **result,
        **analysis.to_dict(),
        **legal_sources,
        "output_validation": output_validation,
    }
