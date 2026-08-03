// Core API의 /ws/audio/operator로 마이크 오디오를 전송합니다.
// 브라우저 MediaRecorder의 webm/opus 대신, 백엔드가 기대하는 8kHz G.711 μ-law
// 바이너리 프레임으로 변환해 선택한 통화에 연결합니다. 백엔드는 외부 전화 레그와
// 오퍼레이터 레그 사이의 오디오를 중계하며, STT 텍스트는 기존 상담 메모 흐름을 유지합니다.

import { CORE_API_BASE_URL, coreAuthHeader } from './coreApiClientV2.js';

const DEFAULT_AUDIO_WS_PATH = '/ws/audio/operator';

function audioWebSocketUrl({ callId, ticket }) {
  const configured = import.meta.env.VITE_AUDIO_WS_URL;
  const endpoint = configured || `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}${DEFAULT_AUDIO_WS_PATH}`;
  const separator = endpoint.includes('?') ? '&' : '?';
  return `${endpoint}${separator}callId=${encodeURIComponent(callId)}&ticket=${encodeURIComponent(ticket)}`;
}

// 외부 전화/SIP 서버가 먼저 등록한 통화 중 상담원이 연결할 수 있는 목록입니다.
// 이미 다른 상담원이 연결한 CONNECTED 상태는 선택지에서 제외합니다.
export async function fetchAvailableAudioCalls() {
  let response;
  try {
    response = await fetch(`${CORE_API_BASE_URL}/api/audio/calls`, {
      headers: coreAuthHeader(),
    });
  } catch {
    throw new Error('진행 중인 통화 목록을 불러올 수 없습니다. Core API 서버 상태를 확인해주세요.');
  }
  if (response.status === 401 || response.status === 403) {
    throw new Error('통화 목록을 조회할 권한이 없습니다. 다시 로그인해주세요.');
  }
  if (!response.ok) {
    throw new Error(`통화 목록을 불러오지 못했습니다.(HTTP ${response.status})`);
  }
  const calls = await response.json();
  return Array.isArray(calls)
    ? calls.filter((call) => call?.callId && call.status === 'WAITING')
    : [];
}

// 소켓에 붙기 전에 1회용 티켓을 받아옵니다.
//
// core-api는 로그인한 사용자만 쓸 수 있게 잠겨 있는데, 브라우저의 new WebSocket()에는
// Authorization 헤더를 넣을 자리가 없습니다. 그래서 헤더를 쓸 수 있는 이 REST 요청으로
// 먼저 티켓을 받고, 그 티켓만 소켓 주소에 실어 보냅니다.
// 주소는 접속 로그·브라우저 히스토리에 남기 때문에 24시간짜리 JWT를 그대로 붙이지 않습니다.
// 티켓은 30초 1회용이라 주소에 남더라도 이미 만료됐거나 소모된 값입니다.
async function requestAudioTicket() {
  let response;
  try {
    response = await fetch(`${CORE_API_BASE_URL}/api/audio/tickets`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...coreAuthHeader() },
    });
  } catch {
    throw new Error('통화 서버에 연결할 수 없습니다. Core API 서버가 켜져 있는지 확인해주세요.');
  }
  if (response.status === 401 || response.status === 403) {
    throw new Error('통화 권한이 없습니다. 다시 로그인해주세요.');
  }
  if (!response.ok) {
    throw new Error(`통화 연결을 준비하지 못했습니다 (HTTP ${response.status})`);
  }
  const body = await response.json();
  if (!body?.ticket) throw new Error('통화 연결 티켓을 받지 못했습니다.');
  return body.ticket;
}

function downsample(buffer, inputSampleRate, outputSampleRate = 8000) {
  if (inputSampleRate === outputSampleRate) return buffer;
  if (inputSampleRate < outputSampleRate) return buffer;
  const ratio = inputSampleRate / outputSampleRate;
  const outputLength = Math.round(buffer.length / ratio);
  const output = new Float32Array(outputLength);
  let offset = 0;
  for (let index = 0; index < outputLength; index += 1) {
    const nextOffset = Math.round((index + 1) * ratio);
    let total = 0;
    let count = 0;
    for (let sourceIndex = offset; sourceIndex < nextOffset && sourceIndex < buffer.length; sourceIndex += 1) {
      total += buffer[sourceIndex];
      count += 1;
    }
    output[index] = count ? total / count : 0;
    offset = nextOffset;
  }
  return output;
}

function linearToMuLaw(sample) {
  const clamped = Math.max(-1, Math.min(1, sample));
  const pcm = clamped < 0 ? clamped * 32768 : clamped * 32767;
  const sign = pcm < 0 ? 0x80 : 0;
  let magnitude = Math.min(32635, Math.abs(pcm));
  magnitude += 132;
  let exponent = 7;
  for (let mask = 0x4000; exponent > 0 && (magnitude & mask) === 0; mask >>= 1) exponent -= 1;
  const mantissa = (magnitude >> (exponent + 3)) & 0x0f;
  return (~(sign | (exponent << 4) | mantissa)) & 0xff;
}

// 서버가 오디오를 받는 것과 별개로 실시간 자막(STT 중간/최종 결과) 텍스트 프레임을 같은
// 소켓으로 돌려보내 줄 때 화면에 뿌리기 위한 자리입니다. 백엔드가 아직 이 프레임을 보내지
// 않아 지금은 항상 빈 채로 남지만(코치 피드백: "실시간 통화 기술" 중 프론트가 먼저 준비해둘
// 수 있는 부분), 백엔드가 붙는 순간 바로 동작하도록 파싱·콜백 구조만 미리 만들어 둡니다.
// 기대하는 프레임 모양: { type: 'transcript', text: string, isFinal?: boolean }
function parseTranscriptFrame(raw) {
  if (typeof raw !== 'string') return null;
  let parsed;
  try {
    parsed = JSON.parse(raw);
  } catch {
    return null;
  }
  if (!parsed || parsed.type !== 'transcript' || typeof parsed.text !== 'string') return null;
  return { text: parsed.text, isFinal: Boolean(parsed.isFinal) };
}

export class RealtimeAudioStream {
  constructor({ onStatus, onError, onTranscript } = {}) {
    this.onStatus = onStatus || (() => {});
    this.onError = onError || (() => {});
    this.onTranscript = onTranscript || (() => {});
    this.socket = null;
    this.mediaStream = null;
    this.audioContext = null;
    this.source = null;
    this.processor = null;
    this.silentGain = null;
  }

  async start({ callId } = {}) {
    if (!navigator.mediaDevices?.getUserMedia) {
      throw new Error('이 브라우저에서는 마이크 입력을 사용할 수 없습니다.');
    }
    if (!callId) {
      throw new Error('연결할 통화를 선택해주세요.');
    }
    this.onStatus('connecting');
    this.mediaStream = await navigator.mediaDevices.getUserMedia({
      audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true },
    });
    try {
      // 티켓은 30초짜리라 연결할 때마다 새로 받습니다(재사용도 막혀 있습니다).
      const ticket = await requestAudioTicket();
      this.socket = new WebSocket(audioWebSocketUrl({ callId, ticket }));
      this.socket.binaryType = 'arraybuffer';
      await new Promise((resolve, reject) => {
        this.socket.addEventListener('open', resolve, { once: true });
        this.socket.addEventListener('error', () => reject(new Error('오디오 스트림 서버에 연결할 수 없습니다.')), { once: true });
      });
      this.socket.addEventListener('close', () => {
        if (this.socket) this.onStatus('ended');
      });
      // 오디오는 binaryType('arraybuffer')로 보내고, 자막 프레임은 텍스트(JSON)로 온다고
      // 가정합니다. 백엔드가 아직 아무 텍스트 프레임도 안 보내므로 지금은 항상 조용히
      // 넘어가지만, 자막 연동이 붙으면 이 리스너가 그대로 받아 화면에 흘려보냅니다.
      this.socket.addEventListener('message', (event) => {
        const transcript = parseTranscriptFrame(event.data);
        if (transcript) this.onTranscript(transcript);
      });

      this.audioContext = new AudioContext();
      await this.audioContext.resume();
      this.source = this.audioContext.createMediaStreamSource(this.mediaStream);
      this.processor = this.audioContext.createScriptProcessor(4096, 1, 1);
      this.silentGain = this.audioContext.createGain();
      this.silentGain.gain.value = 0;
      this.processor.onaudioprocess = (event) => {
        if (!this.socket || this.socket.readyState !== WebSocket.OPEN) return;
        const input = event.inputBuffer.getChannelData(0);
        const samples = downsample(input, this.audioContext.sampleRate, 8000);
        const payload = new Uint8Array(samples.length);
        samples.forEach((sample, index) => { payload[index] = linearToMuLaw(sample); });
        this.socket.send(payload.buffer);
      };
      this.source.connect(this.processor);
      this.processor.connect(this.silentGain);
      this.silentGain.connect(this.audioContext.destination);
      this.onStatus('streaming');
    } catch (error) {
      this.stop();
      throw error;
    }
  }

  stop() {
    if (this.processor) this.processor.disconnect();
    if (this.source) this.source.disconnect();
    if (this.silentGain) this.silentGain.disconnect();
    if (this.audioContext && this.audioContext.state !== 'closed') this.audioContext.close();
    if (this.socket && this.socket.readyState === WebSocket.OPEN) this.socket.close(1000, 'call-ended');
    if (this.mediaStream) this.mediaStream.getTracks().forEach((track) => track.stop());
    this.processor = null;
    this.source = null;
    this.silentGain = null;
    this.audioContext = null;
    this.socket = null;
    this.mediaStream = null;
    this.onStatus('idle');
  }
}

export function createRealtimeAudioStream(options) {
  return new RealtimeAudioStream(options);
}
