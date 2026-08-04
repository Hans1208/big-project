import React, { useEffect, useRef } from 'react';
import { Mic, Volume2 } from 'lucide-react';

// 통화 중 내 음성(마이크)·상대방 음성(재생)의 실시간 크기를 막대로 보여줍니다. RealtimeAudioStream이
// 내부 AnalyserNode로 매 프레임 계산해 둔 값을 requestAnimationFrame으로 읽어와 막대 너비만 DOM에
// 직접 반영합니다 — React state로 올리면 초당 수십 번 이 값이 바뀔 때마다 화면 전체가 리렌더링됩니다.
export function CallAudioVisualizer({ audioStreamRef, active }) {
  const micBarRef = useRef(null);
  const remoteBarRef = useRef(null);

  useEffect(() => {
    if (!active) return undefined;
    let frameId;
    const tick = () => {
      const levels = audioStreamRef.current?.getLevels?.() ?? { mic: 0, remote: 0 };
      // RMS 값은 보통 작아서(정상 발화도 0.1~0.3대) 3배 정도 키워야 막대가 체감상 자연스럽게 움직입니다.
      if (micBarRef.current) micBarRef.current.style.transform = `scaleX(${Math.min(1, levels.mic * 3)})`;
      if (remoteBarRef.current) remoteBarRef.current.style.transform = `scaleX(${Math.min(1, levels.remote * 3)})`;
      frameId = requestAnimationFrame(tick);
    };
    frameId = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frameId);
  }, [active, audioStreamRef]);

  return (
    <div className="callAudioVisualizer">
      <div className="callAudioVisualizerRow">
        <Mic size={13} strokeWidth={2.4} aria-hidden="true" />
        <span className="callAudioVisualizerLabel">내 음성</span>
        <span className="callAudioVisualizerTrack">
          <span ref={micBarRef} className="callAudioVisualizerFill mic" />
        </span>
      </div>
      <div className="callAudioVisualizerRow">
        <Volume2 size={13} strokeWidth={2.4} aria-hidden="true" />
        <span className="callAudioVisualizerLabel">상대방 음성</span>
        <span className="callAudioVisualizerTrack">
          <span ref={remoteBarRef} className="callAudioVisualizerFill remote" />
        </span>
      </div>
    </div>
  );
}
