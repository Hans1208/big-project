import io
import os
import base64
import numpy as np
from pathlib import Path
from fastapi import FastAPI, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from faster_whisper import WhisperModel
from pydub import AudioSegment
from transformers import pipeline

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Vite 개발 서버 (상담원 화면 대면상담 녹음)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = Path(__file__).resolve().parent
HTML_PATH = BASE_DIR / "index.html"

# Load the speech-to-text model. 운영(Modal, modal/backend.py)은 GPU에서 large-v3를 그대로 쓰지만,
# 로컬 개발 PC는 CUDA GPU가 없는 경우가 많아 기본값을 CPU에서도 바로 도는 base 모델로 낮춰둔다.
# GPU가 있는 로컬 환경이면 환경변수로 large-v3/cuda를 그대로 지정해서 쓸 수 있다.
WHISPER_MODEL_SIZE = os.environ.get("WHISPER_MODEL_SIZE", "base")
WHISPER_DEVICE = os.environ.get("WHISPER_DEVICE", "cpu")
WHISPER_COMPUTE_TYPE = os.environ.get("WHISPER_COMPUTE_TYPE", "int8" if WHISPER_DEVICE == "cpu" else "float16")

model = WhisperModel(WHISPER_MODEL_SIZE, device=WHISPER_DEVICE, compute_type=WHISPER_COMPUTE_TYPE)

# Load the OpenAI Privacy Filter
print("Loading OpenAI Privacy Filter...")
privacy_filter = pipeline(
    "token-classification", 
    model="openai/privacy-filter", 
    aggregation_strategy="simple"
)
print("Models loaded successfully.")

@app.get("/")
async def serve_frontend():
    return FileResponse(HTML_PATH)

def redact_text(text: str, spans: list) -> str:
    """Replaces detected PII spans with their label placeholders."""
    result = list(text)
    # Sort descending so earlier string replacements don't shift later indexes
    for span in sorted(spans, key=lambda s: s["start"], reverse=True):
        label = f"[{span['entity_group'].upper()}]"
        # Replace the characters spanning start:end with the characters of the label
        result[span["start"]:span["end"]] = list(label)
    return "".join(result)

@app.post("/transcribe")
async def transcribe_audio(file: UploadFile = File(...)):
    """Receives audio, transcribes it, runs the privacy filter, and returns the data."""
    try:
        audio_bytes = await file.read()
        
        audio_file = io.BytesIO(audio_bytes)
        audio_segment = AudioSegment.from_file(audio_file)
        audio_segment = audio_segment.set_frame_rate(16000).set_channels(1)

        samples = np.array(audio_segment.get_array_of_samples(), dtype=np.float32)
        # sample_width는 보통 2바이트(16비트)지만, 하드코딩된 32768.0 대신 실제 폭 기준으로
        # 정규화한다 — 폭이 다르면 값이 잘못 스케일링돼(클리핑/왜곡) STT 품질이 나빠진다.
        max_value = float(1 << (8 * audio_segment.sample_width - 1))
        audio_array = samples / max_value

        # 1. Run transcription
        # vad_filter=True: 무음/저음량 구간을 Whisper에 그대로 넘기지 않고 먼저 걸러낸다.
        # 5초마다 MediaRecorder를 stop/restart하는 구조라 각 조각 앞부분에 무음(마이크 워밍업)이
        # 섞이기 쉬운데, 이걸 무음 없이 그대로 넣으면 작은 모델(base)이 "아, 그.." 같은 반복
        # 필러를 환각(hallucination)으로 만들어낸다 — 이게 신고된 증상과 정확히 일치한다.
        segments, _ = model.transcribe(audio_array, language="ko", vad_filter=True)
        full_text = " ".join([segment.text for segment in segments]).strip()
        
        # 2. Run Privacy Filter
        if full_text:
            spans = privacy_filter(full_text)
            redacted_text = redact_text(full_text, spans)
        else:
            redacted_text = ""
        
        # 3. Export audio to WAV format
        wav_io = io.BytesIO()
        audio_segment.export(wav_io, format="wav")
        wav_bytes = wav_io.getvalue()
        encoded_audio = base64.b64encode(wav_bytes).decode("utf-8")
        
        return {
            "text": full_text,
            "redacted_text": redacted_text,
            "audio_base64": encoded_audio
        }
        
    except Exception as e:
        # FastAPI는 (본문, 상태코드) 튜플을 Flask처럼 해석하지 않는다 — 그대로 반환하면
        # [{"error": "..."}, 500] 배열이 HTTP 200으로 나가버려 호출하는 쪽(core-api)이 진짜
        # 에러 메시지를 못 읽는다. JSONResponse로 상태코드와 본문을 명시적으로 지정해야 한다.
        return JSONResponse(status_code=500, content={"error": f"{type(e).__name__}: {e}"})