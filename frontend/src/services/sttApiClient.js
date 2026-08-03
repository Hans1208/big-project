// STT 개인정보 마스킹 API 클라이언트입니다.
// 기본 개발 주소는 Vite 프록시(/stt-api)를 사용하고, 배포 환경에서는
// VITE_STT_API_BASE_URL로 실제 STT API 주소를 지정할 수 있습니다.
const STT_API_BASE_URL = import.meta.env.VITE_STT_API_BASE_URL || '/stt-api';
const STT_TIMEOUT_MS = 10 * 60 * 1000;

export async function transcribeAudio(file) {
  if (!(file instanceof File || file instanceof Blob)) {
    throw new Error('STT로 보낼 오디오 파일이 없습니다.');
  }

  const formData = new FormData();
  formData.append('file', file, file.name || 'recording.webm');
  const controller = new AbortController();
  const timeoutId = window.setTimeout(() => controller.abort(), STT_TIMEOUT_MS);

  let response;
  try {
    // multipart 요청은 브라우저가 boundary를 붙이므로 Content-Type을 직접 지정하지 않습니다.
    response = await fetch(`${STT_API_BASE_URL}/transcribe`, {
      method: 'POST',
      body: formData,
      signal: controller.signal,
    });
  } catch (error) {
    if (error.name === 'AbortError') {
      throw new Error('STT 변환 시간이 너무 오래 걸려 요청을 중단했습니다.');
    }
    throw new Error('STT 서버에 연결할 수 없습니다. STT API가 실행 중인지 확인해주세요.');
  } finally {
    window.clearTimeout(timeoutId);
  }

  const data = await response.json().catch(() => null);
  if (!response.ok) {
    throw new Error(data?.detail || data?.error || `STT 요청 실패 (HTTP ${response.status})`);
  }
  if (data?.error) throw new Error(data.error);

  return {
    originalText: data?.original_text ?? data?.text ?? '',
    anonymizedText: data?.anonymized_text ?? data?.redacted_text ?? '',
    anonymizationMap: Array.isArray(data?.anonymization_map) ? data.anonymization_map : [],
    audioBase64: data?.audio_base64 || '',
  };
}

export { STT_API_BASE_URL };
