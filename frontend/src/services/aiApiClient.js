// backend/ai-api(FastAPI) 서버와 통신하는 실제 HTTP 클라이언트입니다.
// legalAidApi.js가 "백엔드 연동 전 임시 목업"이라면, 이 파일은 "실제 백엔드에 연결되는 창구" 역할을 합니다.
// 개발 중에는 Vite 프록시(/ai-api)를 통해 호출해 localhost/127.0.0.1 차이와 CORS 문제를 피합니다.
const AI_API_BASE_URL = import.meta.env.VITE_AI_API_BASE_URL || '/ai-api';

// 엔드포인트별 요청 제한 시간(ms). 지정하지 않으면 기본값을 씁니다.
const DEFAULT_TIMEOUT_MS = 30_000;

// 요청이 timeoutMs를 넘기면 fetch 자체를 중단합니다.
// 이게 없으면 백엔드가 응답 없이 멈춰 있을 때 화면이 '분석 중…' 상태로 무한정 멈춰 보입니다.
// 시간 초과로 끊긴 요청은 호출부(fetchAnalysisWithFallback 등)가 잡아서 다음 대체 경로로 넘어갑니다.
async function requestJson(path, options = {}, timeoutMs = DEFAULT_TIMEOUT_MS) {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

  let response;
  try {
    response = await fetch(`${AI_API_BASE_URL}${path}`, {
      ...options,
      headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
      signal: controller.signal,
    });
  } catch (error) {
    if (error.name === 'AbortError') {
      throw new Error(`AI API 응답이 ${Math.round(timeoutMs / 1000)}초 안에 오지 않아 요청을 중단했습니다.`);
    }
    throw new Error('AI API 서버에 연결할 수 없습니다. ai-api 터미널이 켜져 있는지 확인해주세요.');
  } finally {
    clearTimeout(timeoutId);
  }

  if (!response.ok) {
    const errorDetail = await response.text().catch(() => '');
    if (response.status === 502 || /bad gateway/i.test(errorDetail)) {
      if (path.startsWith('/forms/revisions')) {
        throw new Error(
          'AI API 서버는 연결됐지만 서식 개정 점검 대상에서 응답을 받지 못했습니다 (HTTP 502). '
          + '잠시 후 다시 시도하거나 ai-api 터미널의 서식 점검 오류를 확인해주세요.',
        );
      }
      throw new Error(
        'AI API 서버가 정상 응답하지 않습니다 (HTTP 502). '
        + 'ai-api가 http://127.0.0.1:8001에서 실행 중인지 확인한 뒤 다시 시도해주세요.',
      );
    }
    throw new Error(`AI API 요청 실패 (HTTP ${response.status}): ${errorDetail || response.statusText}`);
  }

  return response.json();
}

// 프론트-백엔드 연결 상태를 확인할 때 사용합니다 (GET /health).
export function checkAiApiHealth() {
  return requestJson('/health');
}

// 참고: 예전에는 여기에 requestContractAnalysis(POST /analysis, 구 계약 mock)와
// requestConsultAnalysis(POST /consult/analyze 직접 호출)도 있었지만, 현재 아키텍처에서는
// core-api가 /consult/analyze 호출을 오케스트레이션하므로(triggerCoreAnalysis 참고) 두 함수 모두
// 프론트 어디서도 쓰이지 않는 죽은 코드였습니다. 그래서 제거했습니다.

// 서식 개정 점검 (요구사항 AI-05-04-01).
// helplaw24 서식 목록 22페이지를 순회하며 받아오므로 기본 제한(30초)으로는 모자랍니다.
const FORM_REVISION_TIMEOUT_MS = 180_000;

// 점검만 합니다. 기준 스냅샷은 바뀌지 않으므로 여러 번 눌러도 결과가 같습니다.
export function checkFormRevisions() {
  return requestJson('/forms/revisions', {}, FORM_REVISION_TIMEOUT_MS);
}

// 관리자가 변경 내용을 확인했다는 표시. 현재 상태가 새 기준선이 되어
// 같은 변경이 다음 점검에서 다시 올라오지 않습니다.
export function acknowledgeFormRevisions() {
  return requestJson('/forms/revisions/acknowledge', { method: 'POST' }, FORM_REVISION_TIMEOUT_MS);
}

// 법령 검색·추천 (ai-api /statutes). 색인은 민법·가사소송법·가족관계등록법·
// 민사소송법·민사집행법의 조문 2,258개를 담고 있어, 결과는 법령 단위가 아니라
// 조문 단위(예: "민법 제1091조(유언증서, 녹음의 검인)")로 나옵니다.
//
// 임베딩 모델을 처음 부를 때 로딩이 있어 첫 요청만 느립니다.
const STATUTE_TIMEOUT_MS = 60_000;

// 상담원이 직접 넣은 검색어로 조문을 찾습니다.
export function searchStatutes({ query, lawId = '', topK = 5 }) {
  return requestJson('/statutes/search', {
    method: 'POST',
    body: JSON.stringify({ query, law_id: lawId || null, top_k: topK }),
  }, STATUTE_TIMEOUT_MS);
}

// 상담 분석 결과로 관련 조문을 추천합니다. 추천은 후보일 뿐이고 어떤 조문을
// 근거로 쓸지는 상담원·변호사가 정합니다(HITL) — 그래서 유사도와 근거를 함께 받습니다.
export function recommendStatutes(analysis, { topK = 5 } = {}) {
  return requestJson('/statutes/recommend', {
    method: 'POST',
    body: JSON.stringify({
      case_type: analysis?.caseType || analysis?.case_type || '',
      case_subtype: analysis?.caseSubtype || analysis?.case_subtype || '',
      summary: analysis?.summary || '',
      extracted_json: analysis?.extractedJson || analysis?.extracted_json || {},
      top_k: topK,
    }),
  }, STATUTE_TIMEOUT_MS);
}

// 판례 검색·추천 (ai-api /precedents). 색인은 2016년 이후 가사·이혼·상속·친족
// 판례를 담고, 한 사건을 판시사항·요약·전문으로 쪼개 넣습니다. 응답은 사건 단위로
// 중복을 걷어낸 뒤 나오므로 같은 사건이 여러 줄로 나오지 않습니다.
//
// 카드 키(id/title/content/effective_date/similarity_percent/source)는 법령과
// 같습니다. 화면이 탭마다 다른 키를 알 필요가 없게 맞춰 둔 것입니다 —
// effective_date 자리에는 선고일이, source 자리에는 법원명이 들어옵니다.
const PRECEDENT_TIMEOUT_MS = 60_000;

// 상담원이 직접 넣은 검색어로 판례를 찾습니다.
export function searchPrecedents({ query, courtLevel = '', topK = 5 }) {
  return requestJson('/precedents/search', {
    method: 'POST',
    body: JSON.stringify({ query, court_level: courtLevel || null, top_k: topK }),
  }, PRECEDENT_TIMEOUT_MS);
}

// 상담 분석 결과로 관련 판례를 추천합니다. 조문과 마찬가지로 후보 제시일 뿐이라
// 근거(reason)를 함께 받습니다. 판례는 사실관계가 조금만 달라도 결론이 뒤집혀서,
// 근거 없이 목록만 보면 상담원이 반대 결론의 판례를 골라 쓸 수 있습니다.
export function recommendPrecedents(analysis, { topK = 5 } = {}) {
  return requestJson('/precedents/recommend', {
    method: 'POST',
    body: JSON.stringify({
      case_type: analysis?.caseType || analysis?.case_type || '',
      case_subtype: analysis?.caseSubtype || analysis?.case_subtype || '',
      summary: analysis?.summary || '',
      extracted_json: analysis?.extractedJson || analysis?.extracted_json || {},
      top_k: topK,
    }),
  }, PRECEDENT_TIMEOUT_MS);
}

export { AI_API_BASE_URL };
