// backend/ai-api(FastAPI) 서버와 통신하는 실제 HTTP 클라이언트입니다.
// legalAidApi.js가 "백엔드 연동 전 임시 목업"이라면, 이 파일은 "실제 백엔드에 연결되는 창구" 역할을 합니다.
// 개발 중에는 Vite 프록시(/ai-api)를 통해 호출해 localhost/127.0.0.1 차이와 CORS 문제를 피합니다.
const AI_API_BASE_URL = import.meta.env.VITE_AI_API_BASE_URL || '/ai-api';

// 모든 요청이 공통으로 거치는 낮은 수준의 통신 처리(요청 전송, 응답 검증, 에러 메시지 구성)를 한곳에 모읍니다.
async function requestJson(path, options = {}) {
  let response;
  try {
    response = await fetch(`${AI_API_BASE_URL}${path}`, {
      headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
      ...options,
    });
  } catch {
    throw new Error('AI API 서버에 연결할 수 없습니다. ai-api 터미널이 켜져 있는지 확인해주세요.');
  }

  if (!response.ok) {
    const errorDetail = await response.text().catch(() => '');
    throw new Error(`AI API 요청 실패 (HTTP ${response.status}): ${errorDetail || response.statusText}`);
  }

  return response.json();
}

// 프론트-백엔드 연결 상태를 확인할 때 사용합니다 (GET /health).
export function checkAiApiHealth() {
  return requestJson('/health');
}

// FE/BE/AI 모델 팀이 합의한 AI_ANALYSIS 계약(contracts/ai_analysis_mock.json) 기준 분석 요청입니다 (POST /analysis).
// 실제 모델이 아직 붙기 전까지는 고정된 샘플을 반환하지만, 별도 API 키 없이도 항상 성공하는 실제 네트워크 호출입니다.
export function requestContractAnalysis(payload) {
  return requestJson('/analysis', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

// 등록된 상담을 실제 LangGraph 분석 파이프라인으로 보냅니다 (POST /case-analysis).
// 주의: 이 엔드포인트는 실제 OpenAI API 키가 유효해야 정상 동작합니다.
export function requestCaseAnalysis(content) {
  return requestJson('/case-analysis', {
    method: 'POST',
    body: JSON.stringify({ content }),
  });
}

// 법률구조 대상자 요건을 분석합니다 (POST /eligibility/analyze).
// 주의: 이 엔드포인트 역시 실제 OpenAI API 키가 유효해야 정상 동작합니다.
export function requestEligibilityAnalysis(payload) {
  return requestJson('/eligibility/analyze', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

// /eligibility/analyze 결과를 이어받아 누락자료/추가조사 항목을 분석합니다. (POST /missing-data/analyze)
export function requestMissingDataAnalysis(payload) {
  return requestJson('/missing-data/analyze', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export { AI_API_BASE_URL };
