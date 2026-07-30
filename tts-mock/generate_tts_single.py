"""
법률상담 20분 대본 -> TTS 음성 파일 생성 스크립트 (단일 대화용)
================================================================

"상담원:" / "내담자:" 두 화자로만 구성된 단일 대화 파일을 읽어, 발화 단위로
TTS 음성을 생성한 뒤 하나의 음성 파일로 이어 붙입니다.

원본 스크립트와 달라진 점 (Windows 환경 대응)
--------------------------------------------
- pydub / ffmpeg를 쓰지 않는다.
  pydub이 의존하는 audioop 모듈이 Python 3.13에서 표준 라이브러리에서 빠졌고,
  ffmpeg도 별도 설치가 필요하다. OpenAI TTS에서 mp3 대신 wav로 받으면
  표준 라이브러리 wave 모듈만으로 이어 붙일 수 있어서 둘 다 필요 없어진다.
  결과물을 mp3로 원하면 ffmpeg가 있을 때만 자동 변환한다(--format mp3).
- 이미 만들어둔 발화 파일은 건너뛴다. 54턴을 돌리다 중간에 끊겨도
  다시 실행하면 남은 것부터 이어서 생성한다(--no-resume으로 끌 수 있음).
- OPENAI_API_KEY를 환경변수에서 못 찾으면 .env 파일에서도 찾아본다.

사용 전 준비
------------
pip install openai
(pydub, ffmpeg 불필요. --format mp3 를 쓸 때만 ffmpeg 필요)

API 키는 아래 중 하나로 준비:
  1) PowerShell 영구 등록 (터미널을 새로 열어야 적용됨)
     [Environment]::SetEnvironmentVariable("OPENAI_API_KEY", "sk-...", "User")
  2) 현재 창에서만
     $env:OPENAI_API_KEY = "sk-..."
  3) .env 파일에 OPENAI_API_KEY=sk-... 한 줄 (--env-file로 경로 지정)

사용 예시
---------
python generate_tts_single.py --input 법률상담_20분_대본_상속.md --dry-run
python generate_tts_single.py --input 법률상담_20분_대본_상속.md
python generate_tts_single.py --input 법률상담_20분_대본_상속.md \
    --counselor-voice nova --client-voice onyx --outdir ./mock_audio
"""

import argparse
import os
import re
import shutil
import subprocess
import sys
import wave
from pathlib import Path

TURN_RE = re.compile(r"^(상담원|내담자)\s*:\s*(.+)$")

# 기본 .env 후보 — 이 프로젝트의 ai-api가 이미 OPENAI_API_KEY를 갖고 있어서
# 별도로 키를 등록하지 않아도 바로 돌려볼 수 있게 해둔다.
DEFAULT_ENV_CANDIDATES = [
    Path(__file__).parent / ".env",
    Path(__file__).parents[1] / "backend" / "ai-api" / ".env",
]


def parse_turns(md_text: str):
    """마크다운에서 '상담원:'/'내담자:' 발화만 순서대로 추출"""
    turns = []
    for line in md_text.splitlines():
        match = TURN_RE.match(line.strip())
        if match:
            speaker, text = match.groups()
            turns.append((speaker, text.strip()))
    return turns


def estimate_minutes(turns, chars_per_minute=300):
    total_chars = sum(len(text) for _, text in turns)
    return total_chars, total_chars / chars_per_minute


def load_api_key(env_file: str | None) -> str | None:
    """환경변수 -> .env 순서로 OPENAI_API_KEY를 찾는다. 값은 절대 출력하지 않는다."""
    key = os.environ.get("OPENAI_API_KEY")
    if key:
        return key.strip()

    candidates = [Path(env_file)] if env_file else DEFAULT_ENV_CANDIDATES
    for path in candidates:
        if not path.is_file():
            continue
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if line.startswith("OPENAI_API_KEY="):
                value = line.split("=", 1)[1].strip().strip('"').strip("'")
                if value:
                    print(f"  API 키를 {path} 에서 읽었습니다.")
                    return value
    return None


class OpenAITTSClient:
    def __init__(self, api_key, counselor_voice="nova", client_voice="onyx", model="tts-1"):
        from openai import OpenAI

        self.client = OpenAI(api_key=api_key)
        self.model = model
        self.voice_map = {"상담원": counselor_voice, "내담자": client_voice}

    def synthesize(self, speaker: str, text: str, out_path: Path):
        voice = self.voice_map.get(speaker, "alloy")
        # wav로 받아야 표준 wave 모듈로 이어 붙일 수 있다.
        with self.client.audio.speech.with_streaming_response.create(
            model=self.model,
            voice=voice,
            input=text,
            response_format="wav",
        ) as response:
            response.stream_to_file(str(out_path))


def concat_wavs(wav_paths, out_path: Path, silence_ms: int):
    """표준 wave 모듈로 wav들을 이어 붙이고 사이에 무음을 넣는다.

    주의: setparams(reader.getparams())로 통째로 복사하면 안 된다.
    OpenAI가 wav를 스트리밍으로 내려줄 때 헤더의 데이터 길이를 placeholder(0xFFFFFFFF)로
    채워 보내는데, 그 값이 nframes로 딸려 들어가면 최종 헤더를 쓸 때 4바이트 정수 범위를
    넘겨서 struct.error가 난다. 포맷 정보만 가져오고 길이는 wave 모듈이 직접 세게 둔다.
    같은 이유로 readframes(getnframes())도 못 믿으니 EOF까지 청크로 읽는다.
    """
    with wave.open(str(out_path), "wb") as writer:
        params_set = False
        silence_frames = b""

        for idx, path in enumerate(wav_paths):
            with wave.open(str(path), "rb") as reader:
                if not params_set:
                    writer.setnchannels(reader.getnchannels())
                    writer.setsampwidth(reader.getsampwidth())
                    writer.setframerate(reader.getframerate())
                    frame_size = reader.getsampwidth() * reader.getnchannels()
                    silence_frames = b"\x00" * (
                        int(reader.getframerate() * silence_ms / 1000) * frame_size
                    )
                    params_set = True

                while True:
                    chunk = reader.readframes(4096)
                    if not chunk:
                        break
                    writer.writeframes(chunk)

            if idx < len(wav_paths) - 1 and silence_frames:
                writer.writeframes(silence_frames)


def wav_duration_seconds(path: Path) -> float:
    with wave.open(str(path), "rb") as reader:
        return reader.getnframes() / reader.getframerate()


def convert_to_mp3(wav_path: Path) -> Path | None:
    """ffmpeg가 있으면 mp3로 변환. 없으면 None을 돌려주고 wav를 그대로 쓴다."""
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return None
    mp3_path = wav_path.with_suffix(".mp3")
    subprocess.run(
        [ffmpeg, "-y", "-loglevel", "error", "-i", str(wav_path), str(mp3_path)],
        check=True,
    )
    return mp3_path


def build_full_audio(turns, tts_client, outdir: Path, base_name: str, silence_ms: int,
                     resume: bool):
    turns_dir = outdir / f"{base_name}_turns"
    turns_dir.mkdir(parents=True, exist_ok=True)

    wav_paths = []
    for idx, (speaker, text) in enumerate(turns, start=1):
        turn_path = turns_dir / f"{idx:03d}_{speaker}.wav"
        if resume and turn_path.exists() and turn_path.stat().st_size > 0:
            print(f"  [{idx:03d}/{len(turns)}] 건너뜀(이미 있음)")
        else:
            print(f"  [{idx:03d}/{len(turns)}] {speaker}: {text[:24]}...")
            tts_client.synthesize(speaker, text, turn_path)
        wav_paths.append(turn_path)

    final_wav = outdir / f"{base_name}.wav"
    concat_wavs(wav_paths, final_wav, silence_ms)
    return final_wav


def main():
    parser = argparse.ArgumentParser(description="단일 상담 대본을 TTS 음성으로 변환")
    parser.add_argument("--input", default="법률상담_20분_대본_상속.md", help="대본 마크다운 파일 경로")
    parser.add_argument("--outdir", default="./mock_audio", help="출력 폴더")
    parser.add_argument("--counselor-voice", default="nova", help="상담원 voice")
    parser.add_argument("--client-voice", default="onyx", help="내담자 voice")
    parser.add_argument("--model", default="tts-1", help="tts-1 또는 tts-1-hd")
    parser.add_argument("--silence-ms", type=int, default=400, help="발화 사이 정적(ms)")
    parser.add_argument("--format", choices=["wav", "mp3"], default="mp3",
                        help="최종 출력 형식. mp3는 ffmpeg가 있을 때만 가능(없으면 wav로 남김)")
    parser.add_argument("--env-file", default=None, help="OPENAI_API_KEY를 읽을 .env 경로")
    parser.add_argument("--no-resume", action="store_true", help="이미 만든 발화 파일도 다시 생성")
    parser.add_argument("--dry-run", action="store_true", help="API 호출 없이 파싱 결과만 확인")
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"입력 파일을 찾을 수 없습니다: {input_path}", file=sys.stderr)
        sys.exit(1)

    md_text = input_path.read_text(encoding="utf-8")
    turns = parse_turns(md_text)

    if not turns:
        print("대본에서 '상담원:' / '내담자:' 형식의 발화를 찾지 못했습니다.", file=sys.stderr)
        sys.exit(1)

    total_chars, est_minutes = estimate_minutes(turns)
    counselor_turns = sum(1 for s, _ in turns if s == "상담원")
    print(f"총 발화 수: {len(turns)}개 (상담원 {counselor_turns} / 내담자 {len(turns) - counselor_turns})")
    print(f"총 글자 수(발화 본문 기준): {total_chars}자")
    print(f"예상 재생 시간(정적 제외): 약 {est_minutes:.1f}분\n")

    if args.dry_run:
        print("dry-run 모드입니다. 실제 음성 생성은 건너뜁니다.")
        print("\n앞부분 미리보기:")
        for idx, (speaker, text) in enumerate(turns[:5], start=1):
            print(f"  [{idx:03d}] {speaker}: {text[:40]}...")
        return

    api_key = load_api_key(args.env_file)
    if not api_key:
        print("OPENAI_API_KEY를 찾지 못했습니다.", file=sys.stderr)
        print('PowerShell: $env:OPENAI_API_KEY = "sk-..."', file=sys.stderr)
        print("또는 --env-file 로 .env 경로를 지정하세요.", file=sys.stderr)
        sys.exit(1)

    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    base_name = input_path.stem

    tts_client = OpenAITTSClient(
        api_key=api_key,
        counselor_voice=args.counselor_voice,
        client_voice=args.client_voice,
        model=args.model,
    )

    print("음성 생성을 시작합니다...\n")
    final_wav = build_full_audio(
        turns, tts_client, outdir, base_name, args.silence_ms, resume=not args.no_resume
    )
    duration_sec = wav_duration_seconds(final_wav)

    final_path = final_wav
    if args.format == "mp3":
        mp3_path = convert_to_mp3(final_wav)
        if mp3_path:
            final_path = mp3_path
        else:
            print("\nffmpeg가 없어서 mp3 변환을 건너뜁니다. wav로 남깁니다.")
            print("mp3가 필요하면: winget install Gyan.FFmpeg")

    print(f"\n생성 완료: {final_path}")
    print(f"실제 오디오 길이: {duration_sec/60:.1f}분")


if __name__ == "__main__":
    main()
