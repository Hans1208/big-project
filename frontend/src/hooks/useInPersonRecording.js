// 대면 상담 녹음 → mic-stt 실시간 웹소켓(/ws/consult) 연동 훅.
// 이 서버는 whisper-1(파일 기반 API)을 쓰기 때문에 진짜 스트리밍 대신, MediaRecorder를
// 5초마다 stop→restart 해서 "그 자체로 완결된" 오디오 조각을 만들어 binary로 보내는 방식을
// 쓴다(서버 README의 준실시간 청크 방식과 동일). 녹음 종료 시 {"type":"end"}를 보내면 서버가
// 전체 대화 기준 최종 판정(final_result)을 내려준다.

import { useEffect, useRef, useState } from 'react';

const CHUNK_INTERVAL_MS = 5000;

// mic-stt 서버 주소는 VPC 내부망일 수 있어 하드코딩하지 않고, coreApiClientV2.js/
// realtimeAudioStream.js와 같은 방식으로 환경변수에서 읽는다.
export const MIC_STT_WS_URL = import.meta.env.VITE_MIC_STT_WS_URL || 'ws://127.0.0.1:8002/ws/consult';

export function useInPersonRecording({ wsUrl }) {
  const [status, setStatus] = useState('idle'); // idle | connecting | recording | processing | done | error
  const [sttResult, setSttResult] = useState(null); // 서버 final_result.result 그대로 보관
  const [errorMessage, setErrorMessage] = useState(null);

  const wsRef = useRef(null);
  const streamRef = useRef(null);
  const recorderRef = useRef(null);
  const chunkTimerRef = useRef(null);
  const stoppingRef = useRef(false); // true가 되면 청크를 이어가지 않고 마지막 조각 → end만 보낸다

  useEffect(() => () => cleanupMedia(), []);

  function cleanupMedia() {
    if (chunkTimerRef.current) clearTimeout(chunkTimerRef.current);
    if (recorderRef.current && recorderRef.current.state !== 'inactive') recorderRef.current.stop();
    streamRef.current?.getTracks().forEach((track) => track.stop());
    wsRef.current?.close();
  }

  // 5초짜리 독립 오디오 조각을 하나 녹음해서 ws로 보내고, 다음 조각을 이어서 시작한다.
  function beginChunk() {
    const recorder = new MediaRecorder(streamRef.current);
    recorderRef.current = recorder;

    recorder.ondataavailable = (event) => {
      if (event.data.size > 0 && wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current.send(event.data);
      }
    };

    recorder.onstop = () => {
      if (stoppingRef.current) {
        wsRef.current?.send(JSON.stringify({ type: 'end' }));
        streamRef.current?.getTracks().forEach((track) => track.stop());
      } else {
        beginChunk();
      }
    };

    recorder.start();
    chunkTimerRef.current = setTimeout(() => {
      if (recorderRef.current?.state === 'recording') recorderRef.current.stop();
    }, CHUNK_INTERVAL_MS);
  }

  const startRecording = async () => {
    setStatus('connecting');
    setErrorMessage(null);
    stoppingRef.current = false;

    let stream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch {
      setStatus('error');
      setErrorMessage('마이크에 연결할 수 없습니다. 브라우저 마이크 권한을 확인해주세요.');
      return;
    }
    streamRef.current = stream;

    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => {
      if (stoppingRef.current) {
        ws.send(JSON.stringify({ type: 'end' }));
        return;
      }
      setStatus('recording');
      beginChunk();
    };

    ws.onmessage = (event) => {
      let payload;
      try {
        payload = JSON.parse(event.data);
      } catch {
        return;
      }
      // partial_transcript/chunk_error: 이번 범위에서는 화면에 실시간 반영하지 않고
      // 최종 판정(final_result)만 상담 메모/참고 배지에 쓴다.
      if (payload.type === 'final_result') {
        if (payload.error) {
          setStatus('error');
          setErrorMessage(payload.error);
        } else {
          setSttResult(payload.result);
          setStatus('done');
        }
        ws.close();
      }
    };

    ws.onerror = () => {
      setStatus('error');
      setErrorMessage('녹음 서버 연결 오류');
    };

    ws.onclose = () => {
      // 정상 종료(status === 'done')가 아닌 상태에서 닫히면 오류로 처리
      setStatus((prev) => (prev === 'done' ? prev : 'error'));
    };
  };

  const stopRecording = () => {
    if (stoppingRef.current || !wsRef.current) return;
    stoppingRef.current = true;
    setStatus('processing');
    if (chunkTimerRef.current) clearTimeout(chunkTimerRef.current);

    if (recorderRef.current?.state === 'recording') {
      recorderRef.current.stop(); // onstop에서 마지막 조각 전송 + end 신호
    } else {
      // 아직 청크 레코더가 시작되기 전(연결 대기 중)이면 바로 정리
      streamRef.current?.getTracks().forEach((track) => track.stop());
      if (wsRef.current.readyState === WebSocket.OPEN) {
        wsRef.current.send(JSON.stringify({ type: 'end' }));
      } else {
        wsRef.current.close();
      }
    }
  };

  return { status, sttResult, errorMessage, startRecording, stopRecording };
}
