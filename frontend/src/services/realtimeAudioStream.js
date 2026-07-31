// Core API의 /ws/audio/mulaw로 마이크 오디오를 전송합니다.
// 브라우저 MediaRecorder의 webm/opus 대신, 백엔드가 기대하는 8kHz G.711 μ-law
// 바이너리 프레임으로 변환해 보냅니다. 현재 백엔드는 수신·PCM 디코딩까지만 하므로
// 이 모듈은 전송 상태를 제공하고, STT 텍스트는 기존 상담 메모 흐름을 유지합니다.

import { CORE_API_BASE_URL, coreAuthHeader } from './coreApiClientV2.js';

const DEFAULT_AUDIO_WS_PATH = '/ws/audio/mulaw';

function audioWebSocketUrl() {
  const configured = import.meta.env.VITE_AUDIO_WS_URL;
  if (configured) return configured;
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  return `${protocol}//${window.location.host}${DEFAULT_AUDIO_WS_PATH}`;
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

export class RealtimeAudioStream {
  constructor({ onStatus, onError } = {}) {
    this.onStatus = onStatus || (() => {});
    this.onError = onError || (() => {});
    this.socket = null;
    this.mediaStream = null;
    this.audioContext = null;
    this.source = null;
    this.processor = null;
    this.silentGain = null;
  }

  async start() {
    if (!navigator.mediaDevices?.getUserMedia) {
      throw new Error('이 브라우저에서는 마이크 입력을 사용할 수 없습니다.');
    }
    this.onStatus('connecting');
    this.mediaStream = await navigator.mediaDevices.getUserMedia({
      audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true },
    });
    try {
      // 티켓은 30초짜리라 연결할 때마다 새로 받습니다(재사용도 막혀 있습니다).
      const ticket = await requestAudioTicket();
      this.socket = new WebSocket(`${audioWebSocketUrl()}?ticket=${encodeURIComponent(ticket)}`);
      this.socket.binaryType = 'arraybuffer';
      await new Promise((resolve, reject) => {
        this.socket.addEventListener('open', resolve, { once: true });
        this.socket.addEventListener('error', () => reject(new Error('오디오 스트림 서버에 연결할 수 없습니다.')), { once: true });
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
