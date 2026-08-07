import asyncio

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
    extracted = await asyncio.to_thread(
        stt_extract.extract_all,
        file_links,
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
    analysis = await asyncio.to_thread(
        analysis_service.analyze,
        consult_text,
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

    graph_state = {
        "content": safe_content,
        "extracted": {
            "texts": [
                scrub(text)
                for text
                in (extracted.texts or [])
            ],
            "details": extracted.details,
            "text": scrub(
                extracted.text or ""
            ),
        },
    }

    # The graph and RAG search are independent.
    # Run the async graph and blocking RAG search
    # concurrently without weakening the RAG
    # anonymized-text privacy boundary.
    result, legal_sources = (
        await asyncio.gather(
            run_consult_analysis(
                graph_state
            ),
            asyncio.to_thread(
                collect_related_legal_sources,
                content=content,
                top_n=5,
            ),
        )
    )

    # Output validation may load and execute
    # local model code, so keep it off the
    # event-loop thread as well.
    output_validation = (
        await asyncio.to_thread(
            validate_consultation_output,
            analysis_output=(
                analysis_service
                .without_draft_contact(
                    analysis.output
                )
            ),
            legal_sources=legal_sources,
        )
    )

    return {
        **result,
        **analysis.to_dict(),
        **legal_sources,
        "output_validation": output_validation,
    }
