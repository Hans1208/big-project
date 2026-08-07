"""
로컬 개발 확인용 스크립트: 실제 SIP 게이트웨이가 없어도 /ws/audio/external에
가짜 통화를 등록해서, 상담원 화면(RealtimeAnalysisPanel) ~ core-api(CallRegistry)
~ 오디오 릴레이 경로가 실제로 동작하는지 눈(귀)으로 확인합니다.

이 스크립트는 "전화 연동"이 아닙니다. 실제 전화망(SIP 트렁크 등)과는 무관하며,
core-api가 기대하는 외부 레그 프로토콜(8kHz μ-law 바이너리 프레임)을 흉내 내는
테스트 클라이언트일 뿐입니다.

사전 준비:
  1) core-api(Spring Boot)가 8080 포트에서 떠 있어야 합니다.
  2) AUDIO_EXTERNAL_API_KEY를 core-api와 동일하게 맞춥니다.
     .env에 따로 안 정했다면 application.yaml 기본값
     (dev-only-external-audio-key-change-me)을 그대로 쓰면 됩니다.

사용법:
  python mock_external_call.py --call-id test-call-1
"""

import argparse
import asyncio
import audioop
import math
import struct

import websockets

DEFAULT_KEY = "dev-only-external-audio-key-change-me"
SAMPLE_RATE = 8000
FRAME_SAMPLES = 160  # 20ms @ 8kHz — G.711 표준 프레임 크기, 실시간감을 위해 이 페이스로 전송


def build_tone_frame(sample_index, frequency=440.0):
    """20ms 분량의 사인파 PCM(16bit) 샘플을 만들고 μ-law로 인코딩합니다.
    (상담원 화면에서 '삐-' 소리가 들리면 정상적으로 연결·전송된 것입니다.)"""
    pcm = bytearray()
    for i in range(FRAME_SAMPLES):
        t = (sample_index + i) / SAMPLE_RATE
        value = int(12000 * math.sin(2 * math.pi * frequency * t))
        pcm += struct.pack('<h', value)
    return audioop.lin2ulaw(bytes(pcm), 2)


async def send_loop(ws):
    """20ms마다 톤 프레임을 보냅니다. 실제 통화처럼 실시간 페이싱을 지킵니다
    (한꺼번에 다 보내면 상담원 쪽 재생 큐가 밀려버립니다)."""
    sample_index = 0
    while True:
        frame = build_tone_frame(sample_index)
        await ws.send(frame)
        sample_index += FRAME_SAMPLES
        await asyncio.sleep(FRAME_SAMPLES / SAMPLE_RATE)


async def recv_loop(ws):
    """상담원(operator) 쪽에서 오는 마이크 오디오를 받아 누적 바이트 수만 출력합니다.
    이 숫자가 계속 늘어나면 상담원 → 외부 레그 방향 릴레이도 정상 동작하는 것입니다."""
    total_bytes = 0
    async for message in ws:
        if isinstance(message, (bytes, bytearray)):
            total_bytes += len(message)
            print(f"\r상담원 쪽에서 수신: 누적 {total_bytes} bytes", end="", flush=True)


async def main():
    parser = argparse.ArgumentParser(description="/ws/audio/external 가짜 통화 발신 테스트 스크립트")
    parser.add_argument("--call-id", default="test-call-1", help="상담원 화면 목록에 뜰 통화 ID")
    parser.add_argument("--host", default="localhost:8080", help="core-api 주소 (host:port)")
    parser.add_argument("--key", default=DEFAULT_KEY, help="AUDIO_EXTERNAL_API_KEY 값")
    args = parser.parse_args()

    url = f"ws://{args.host}/ws/audio/external?callId={args.call_id}"
    headers = {"Authorization": f"Bearer {args.key}"}

    print(f"연결 시도: {url}")
    async with websockets.connect(url, additional_headers=headers) as ws:
        print(f"연결 성공 — callId={args.call_id}")
        print("상담원 화면에서 '새로고침' 후 이 통화 ID를 선택하고 '통화 시작'을 누르세요.")
        print("Ctrl+C로 종료하면 통화가 끊긴 것으로 처리됩니다 (external 세션 종료).\n")
        await asyncio.gather(send_loop(ws), recv_loop(ws))


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n종료합니다.")
    except websockets.exceptions.InvalidStatus as error:
        print(f"연결 거부됨: {error}")
        print("→ core-api가 떠 있는지, AUDIO_EXTERNAL_API_KEY가 일치하는지 확인해주세요.")
