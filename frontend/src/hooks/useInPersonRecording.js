// 대면 상담 녹음 → core-api /ws/audio/in-person 연동 훅.
//
// 전화 실시간 상담(realtimeAudioStream.js, /ws/audio/operator)과 같은 구조를 씁니다: 브라우저의
// new WebSocket()에는 Authorization 헤더를 실을 수 없어서, 먼저 인증된 REST 요청으로 1회성 티켓을
// 받고(POST /api/audio/tickets) 그 티켓만 소켓 주소에 실어 붙습니다.
//
// STT/마스킹 자체는 core-api가 대신 해 줍니다(InPersonRecordingWebSocketHandler가 받은 오디오
// 조각을 stt-mask-api로 넘김) — 이전엔 존재하지 않는 외부 mic-stt(8000번 포트)에 직접 붙어
// segments/ai_judge/validation을 받는 구조였는데, 그 서버가 이 레포 어디에도 없어 실제로는
// 동작하지 않았습니다. 이제는 core-api가 서버 간 호출로 처리하므로 실제로 마스킹이 됩니다.
//
// 이 서버(stt-mask-api)는 whisper-1(파일 기반 API)을 쓰기 때문에 진짜 스트리밍 대신, MediaRecorder를
// 5초마다 stop→restart 해서 "그 자체로 완결된" 오디오 조각을 만들어 binary로 보내는 방식을 씁니다.
// 각 조각은 core-api에서 바로 처리되어 {type:'segment_result', idx, text, maskedText}로 돌아옵니다.
// 녹음 종료 시 {"type":"end"}를 보내면, 그 시점까지 받은 조각이 모두 처리된 뒤(같은 소켓이라 순서가
// 보장됨) {"type":"done"}이 돌아옵니다 — 이때 비로소 상태를 'done'으로 바꿉니다.

import { useEffect, useRef, useState } from 'react';
import { CORE_API_BASE_URL, coreAuthHeader } from '../services/coreApiClientV2.js';

const CHUNK_INTERVAL_MS = 5000;
const IN_PERSON_WS_PATH = '/ws/audio/in-person';

// 티켓은 30초짜리라 연결할 때마다 새로 받아야 합니다(재사용도 막혀 있습니다).
async function requestInPersonAudioTicket() {
  let response;
  try {
    response = await fetch(`${CORE_API_BASE_URL}/api/audio/tickets`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...coreAuthHeader() },
    });
  } catch {
    throw new Error('녹음 서버에 연결할 수 없습니다. Core API 서버가 켜져 있는지 확인해주세요.');
  }
  if (response.status === 401 || response.status === 403) {
    throw new Error('녹음 권한이 없습니다. 다시 로그인해주세요.');
  }
  if (!response.ok) {
    throw new Error(`녹음 연결을 준비하지 못했습니다 (HTTP ${response.status})`);
  }
  const body = await response.json();
  if (!body?.ticket) throw new Error('녹음 연결 티켓을 받지 못했습니다.');
  return body.ticket;
}

function inPersonWebSocketUrl({ consultationId, ticket }) {
  const configured = import.meta.env.VITE_IN_PERSON_AUDIO_WS_URL;
  const base = configured || `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}${IN_PERSON_WS_PATH}`;
  const separator = base.includes('?') ? '&' : '?';
  return `${base}${separator}consultationId=${encodeURIComponent(consultationId)}&ticket=${encodeURIComponent(ticket)}`;
}

export function useInPersonRecording({ consultationId }) {
  const [status, setStatus] = useState('idle'); // idle | connecting | recording | processing | done | error
  // idx별 { text, maskedText } 또는 실패 시 { error } — 순서 보장 없이 도착할 수 있어 idx로 모읍니다.
  const [segments, setSegments] = useState([]);
  const [errorMessage, setErrorMessage] = useState(null);

  const wsRef = useRef(null);
  const streamRef = useRef(null);
  const recorderRef = useRef(null);
  const chunkTimerRef = useRef(null);
  const stoppingRef = useRef(false);

  useEffect(() => () => cleanupMedia(), []);

  function cleanupMedia() {
    if (chunkTimerRef.current) clearTimeout(chunkTimerRef.current);
    if (recorderRef.current && recorderRef.current.state !== 'inactive') recorderRef.current.stop();
    streamRef.current?.getTracks().forEach((track) => track.stop());
    wsRef.current?.close();
  }

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
    if (!consultationId) {
      setStatus('error');
      setErrorMessage('사건을 먼저 선택해주세요.');
      return;
    }
    setStatus('connecting');
    setErrorMessage(null);
    setSegments([]);
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

    try {
      const ticket = await requestInPersonAudioTicket();
      const ws = new WebSocket(inPersonWebSocketUrl({ consultationId, ticket }));
      wsRef.current = ws;

      ws.addEventListener('open', () => {
        if (stoppingRef.current) {
          ws.send(JSON.stringify({ type: 'end' }));
          return;
        }
        setStatus('recording');
        beginChunk();
      });

      ws.addEventListener('message', (event) => {
        if (typeof event.data !== 'string') return;
        let payload;
        try {
          payload = JSON.parse(event.data);
        } catch {
          return;
        }
        if (payload.type === 'segment_result') {
          setSegments((current) => [...current, { idx: payload.idx, text: payload.text, maskedText: payload.maskedText }]);
        } else if (payload.type === 'segment_error') {
          setSegments((current) => [...current, { idx: payload.idx, error: payload.error }]);
        } else if (payload.type === 'done') {
          setStatus('done');
          ws.close(1000, 'recording-done');
        }
      });

      ws.addEventListener('error', () => {
        setStatus('error');
        setErrorMessage('녹음 서버 연결 오류');
      });

      ws.addEventListener('close', (event) => {
        setStatus((prev) => (prev === 'done' ? prev : (event.code === 1000 ? prev : 'error')));
      });
    } catch (error) {
      cleanupMedia();
      setStatus('error');
      setErrorMessage(error.message || '녹음 서버에 연결할 수 없습니다.');
    }
  };

  const stopRecording = () => {
    if (stoppingRef.current || !wsRef.current) return;
    stoppingRef.current = true;
    setStatus('processing');
    if (chunkTimerRef.current) clearTimeout(chunkTimerRef.current);

    if (recorderRef.current?.state === 'recording') {
      recorderRef.current.stop(); // onstop에서 마지막 조각 전송 + end 신호
    } else {
      streamRef.current?.getTracks().forEach((track) => track.stop());
      if (wsRef.current.readyState === WebSocket.OPEN) {
        wsRef.current.send(JSON.stringify({ type: 'end' }));
      } else {
        wsRef.current.close();
      }
    }
  };

  return { status, segments, errorMessage, startRecording, stopRecording };
}
