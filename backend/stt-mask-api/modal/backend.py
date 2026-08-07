import io
import base64
from pathlib import Path

import modal

app = modal.App("audio-transcribe-privacy")

BASE_DIR = Path(__file__).resolve().parent
HTML_LOCAL_PATH = BASE_DIR / "index.html"
HTML_REMOTE_PATH = "/root/index.html"

image = (
    modal.Image.from_registry("nvidia/cuda:12.4.0-devel-ubuntu22.04", add_python="3.11")
    .apt_install("ffmpeg")
    .uv_pip_install(
        "fastapi[standard]",
        "python-multipart",
        "numpy",
        "faster-whisper",
        "pydub",
        "transformers",
        "torch",
    )
)

# Bundle the frontend into the image if it exists locally.
if HTML_LOCAL_PATH.exists():
    image = image.add_local_file(HTML_LOCAL_PATH, HTML_REMOTE_PATH)

MODEL_DIR = "/models"
volume = modal.Volume.from_name("whisper-models", create_if_missing=True)


@app.cls(
    image=image,
    gpu="A10",
    volumes={MODEL_DIR: volume},
    scaledown_window=300,
    timeout=600,
)
class Backend:
    @modal.enter()
    def load_models(self):
        import os

        # Route the HF Hub cache onto the volume so transformers-based
        # models (e.g. the privacy filter) are only downloaded once.
        os.environ["HF_HOME"] = f"{MODEL_DIR}/hf_cache"

        import numpy as np
        from faster_whisper import WhisperModel
        from transformers import pipeline

        self.np = np

        # Pick up any weights another container already downloaded.
        volume.reload()

        print("Loading speech-to-text model...")
        self.model = WhisperModel(
            "large-v3",
            device="cuda",
            compute_type="float16",
            download_root=f"{MODEL_DIR}/whisper",
        )

        print("Loading OpenAI Privacy Filter...")
        self.privacy_filter = pipeline(
            "token-classification",
            model="openai/privacy-filter",
            aggregation_strategy="simple",
            device="cuda",
        )
        print("Models loaded successfully.")

        # Persist any freshly downloaded weights back to the volume.
        volume.commit()

    @staticmethod
    def anonymize_text(text: str, spans: list) -> tuple[str, list]:
        """Replaces detected PII spans with [index] placeholders.

        Returns the anonymized text along with an anonymization_map list,
        where anonymization_map[i] is the original value behind "[i]".
        """
        ordered_spans = sorted(spans, key=lambda s: s["start"])
        anonymization_map = [text[s["start"]:s["end"]] for s in ordered_spans]

        result = list(text)
        # Replace from the end so earlier replacements don't shift later indexes
        for i in range(len(ordered_spans) - 1, -1, -1):
            span = ordered_spans[i]
            label = f"[{i}]"
            result[span["start"]:span["end"]] = list(label)
        anonymized_text = "".join(result)

        return anonymized_text, anonymization_map

    @modal.asgi_app()
    def web(self):
        import os

        import torch
        from fastapi import FastAPI, File, UploadFile
        from fastapi.middleware.cors import CORSMiddleware
        from fastapi.responses import FileResponse, JSONResponse
        from pydub import AudioSegment

        web_app = FastAPI()

        # 운영 배포 전 반드시 CORS_ALLOWED_ORIGINS 환경변수(Modal Secret 등)로
        # 실제 프론트엔드 도메인으로 교체할 것. 여러 개는 콤마로 구분.
        cors_origins = [
            origin.strip()
            for origin in os.environ.get("CORS_ALLOWED_ORIGINS", "http://localhost:5173").split(",")
            if origin.strip()
        ]

        web_app.add_middleware(
            CORSMiddleware,
            allow_origins=cors_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

        @web_app.get("/")
        async def serve_frontend():
            if Path(HTML_REMOTE_PATH).exists():
                return FileResponse(HTML_REMOTE_PATH)
            return JSONResponse({"error": "index.html not found"}, status_code=404)

        @web_app.post("/transcribe")
        async def transcribe_audio(file: UploadFile = File(...)):
            """Receives audio, transcribes it, runs the privacy filter, and returns the data."""
            try:
                audio_bytes = await file.read()

                audio_file = io.BytesIO(audio_bytes)
                audio_segment = AudioSegment.from_file(audio_file)
                audio_segment = audio_segment.set_frame_rate(16000).set_channels(1)

                samples = self.np.array(audio_segment.get_array_of_samples(), dtype=self.np.float32)
                audio_array = samples / 32768.0

                # 1. Run transcription
                segments, _ = self.model.transcribe(audio_array, language="ko")
                full_text = " ".join([segment.text for segment in segments]).strip()

                # 2. Run Privacy Filter
                if full_text:
                    spans = self.privacy_filter(full_text)
                    anonymized_text, anonymization_map = self.anonymize_text(full_text, spans)
                else:
                    anonymized_text = ""
                    anonymization_map = []

                # 3. Export audio to WAV format
                wav_io = io.BytesIO()
                audio_segment.export(wav_io, format="wav")
                wav_bytes = wav_io.getvalue()
                encoded_audio = base64.b64encode(wav_bytes).decode("utf-8")

                return {
                    "original_text": full_text,
                    "anonymized_text": anonymized_text,
                    "anonymization_map": anonymization_map,
                    "audio_base64": encoded_audio,
                }

            except Exception as e:
                return JSONResponse({"error": str(e)}, status_code=500)

        return web_app
