from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import analysis, forms

from pydantic import BaseModel
from app.agents.case_analysis.graph import run_case_analysis
from app.agents.case_analysis.multimodal import get_whisper_model
from app.agents.rescue_check.graph import eligibility_graph
from app.agents.rescue_check.modal import EligibilityCheckRequest, EligibilityCheckResponse
from app.agents.missing_check.graph import missing_data_graph
from app.agents.missing_check.modal import MissingDataCheckRequest, MissingDataCheckResponse

from app.agents.consult.graph import run_consult_analysis
# from app.agents.consult.multimodal import get_whisper_model ##위의 get_whisper_model과 기능적으로 동일함. 
from app.agents.consult.schemas import ConsultAnalyzeResponse, RawInput

app = FastAPI(title="AI API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Vite 개발 서버
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(analysis.router)
app.include_router(forms.router)


@app.get("/health")
def health():
    return {"status": "ok"}



@app.on_event("startup")
def preload_models():
    """Whisper 모델을 서버 시작 시점에 미리 로드해서,
    첫 요청에서 모델 로딩 때문에 지연되는 것을 방지."""
    get_whisper_model()

class ConsultRequest(BaseModel):
    content: dict

@app.post("/case-analysis")
def analyze(req: ConsultRequest):
    # HITL 원칙: 이 응답은 항상 "검토 대기" 상태로 프론트/DB에 저장되어야 하며,
    # 상담원/변호사/공익법무관의 최종 확정 액션을 거쳐야 함.
    result = run_case_analysis({"content": req.content})
    # return result["case_analysis"]
    return result

#
@app.post("/eligibility/analyze", response_model=EligibilityCheckResponse)
async def analyze_eligibility(payload: EligibilityCheckRequest) -> EligibilityCheckResponse:
    initial_state = payload.to_consult_fields()
    result_state = await eligibility_graph.ainvoke(initial_state)
    return EligibilityCheckResponse(relief_review_checklist=result_state["relief_review_checklist"])

@app.post("/missing-data/analyze", response_model=MissingDataCheckResponse)
async def analyze_missing_data(payload: MissingDataCheckRequest) -> MissingDataCheckResponse:
    initial_state = payload.to_consult_fields()
    result_state = await missing_data_graph.ainvoke(initial_state)
    return MissingDataCheckResponse(missing_items=result_state["missing_items"])

#위의 3개 라우터 통합한 버전
@app.post("/consult/analyze", response_model=ConsultAnalyzeResponse)
async def analyze_consult(payload: RawInput) -> dict:
    """버튼 클릭 1번 = 이 엔드포인트 1회 호출.

    기존에 프론트/Spring이 순서대로 호출하던 3개 엔드포인트
    (/case-analysis -> /eligibility/analyze -> /missing-data/analyze)를
    app.agents.consult 그래프 하나로 통합해, 텍스트+첨부파일을 받아
    사건분석/구조검토 체크리스트/누락자료를 한 번에 반환한다.

    HITL은 이 API 자체의 흐름을 바꾸지 않는다 — 응답은 항상 "검토 대기" 상태로
    프론트/DB에 저장되어야 하며, 상담원/변호사/공익법무관의 최종 확정 액션을 거쳐야 함.
    """
    result = await run_consult_analysis({"content": payload.content.model_dump()})
    return result
