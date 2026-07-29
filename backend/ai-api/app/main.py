"""FastAPI 앱 조립 지점.

엔드포인트 정의는 전부 app/routers/ 아래에 두고 여기서는 등록만 한다.
(예전에는 일부 엔드포인트가 이 파일에 직접 있어서, 경로를 찾으려면
main.py와 routers/ 두 곳을 봐야 했다.)

AI 기능 본체는 app/ai/ 아래에 파이프라인 순서대로 나뉘어 있다:
  stt      음성·문서 -> 텍스트
  analysis 상담 구조화 분석 (AI_ANALYSIS 생성)
  consult  판정 파이프라인 (긴급도·구조대상·누락자료)
  forms    서식 추천·초안·검증
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.ai.stt.multimodal import get_whisper_model
from app.routers import analysis, consult, forms

app = FastAPI(title="AI API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Vite 개발 서버
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(analysis.router)
app.include_router(consult.router)
app.include_router(forms.router)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.on_event("startup")
def preload_models():
    """Whisper 모델을 서버 시작 시점에 미리 로드해서,
    첫 요청에서 모델 로딩 때문에 지연되는 것을 방지."""
    get_whisper_model()
