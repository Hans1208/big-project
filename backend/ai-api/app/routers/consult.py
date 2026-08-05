from fastapi import APIRouter

from app.ai.analysis import service as analysis_service
from app.ai.consult.graph import run_consult_analysis
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

    result = await run_consult_analysis(
        {
            "content": content,
            "extracted": {
                "texts": extracted.texts,
                "details": extracted.details,
                "text": extracted.text,
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

    return {
        **result,
        **analysis.to_dict(),
        **legal_sources,
    }
