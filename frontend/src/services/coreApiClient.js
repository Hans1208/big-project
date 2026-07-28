const CORE_API_BASE_URL = import.meta.env.VITE_CORE_API_BASE_URL || '/core-api';

async function requestCoreJson(path, options = {}) {
  let response;
  try {
    response = await fetch(`${CORE_API_BASE_URL}${path}`, {
      headers: options.body instanceof FormData ? options.headers : { 'Content-Type': 'application/json', ...(options.headers || {}) },
      ...options,
    });
  } catch {
    throw new Error('Core API 서버에 연결할 수 없습니다. Spring Boot 서버가 켜져 있는지 확인해주세요.');
  }

  if (response.status === 204) return null;
  if (!response.ok) {
    const errorDetail = await response.text().catch(() => '');
    throw new Error(`Core API 요청 실패 (HTTP ${response.status}): ${errorDetail || response.statusText}`);
  }

  return response.json();
}

function toCoreRole(role) {
  return role === 'admin' ? 'ADMIN' : 'CONSULTANT';
}

function toCoreAttachmentRegistration(item = {}) {
  return {
    fileName: item.name || '',
    fileType: item.category || '',
    fileKey: item.fileKey || '',
    fileUrl: item.uploadedUrl || '',
    contentType: item.mimeType || '',
  };
}

function toCoreConsultationPayload({ userId, consultation }) {
  return {
    userId,
    title: consultation.title || consultation.caseNo || '상담 제목 미입력',
    inputText: consultation.memo || consultation.title || '',
    opponentName: consultation.opponentName || consultation.name || '',
    category: consultation.category || '',
    type: consultation.type || '',
    legalAidType: consultation.legalAidType || 'none',
    eligibilityEvidenceSubmitted: Boolean(consultation.eligibilityCheck?.evidenceSubmitted),
    // fileKey가 없는 항목(S3 업로드 실패로 로컬 폴백된 파일)은 서버에 등록할 실체가 없으므로 제외합니다.
    attachments: (consultation.attachments || [])
      .filter((item) => item.fileKey)
      .map(toCoreAttachmentRegistration),
  };
}

function normalizeAnalysisAttachment(item = {}) {
  return {
    category: item.category || item.fileType || '',
    fileName: item.name || item.fileName || '',
    fileType: item.mimeType || item.fileType || '',
    storageBucket: item.storageBucket || '',
    fileKey: item.fileKey || item.key || '',
    fileUrl: item.uploadedUrl || item.fileUrl || item.downloadUrl || '',
    status: item.status || '',
  };
}

function buildCoreExtractedJson(analysis = {}) {
  const extractedJson = { ...(analysis.extractedJson || {}) };
  const sourceAttachments = analysis.sourceAttachments?.length ? analysis.sourceAttachments : analysis.attachments || [];
  const attachmentLinks = sourceAttachments
    .map(normalizeAnalysisAttachment)
    .filter((item) => item.fileName || item.fileKey || item.fileUrl);

  if (attachmentLinks.length) {
    extractedJson.attachment_links = attachmentLinks;
    extractedJson.submitted_file_link = attachmentLinks
      .map((item) => item.fileKey || item.fileUrl)
      .filter(Boolean);
  }

  return extractedJson;
}

function toCoreAnalysisPayload(analysis = {}) {
  return {
    summary: analysis.summary || '',
    case_type: analysis.caseType || '',
    case_subtype: analysis.caseSubtype || '',
    urgency_level: analysis.urgency || '',
    eligibility: analysis.eligibility || '',
    extracted_json: buildCoreExtractedJson(analysis),
    missing_info_json: analysis.missingInfo || [],
    checklist_json: (analysis.checklist || []).map((item) => ({ 항목: item.label, 결과: item.checked ? '충족' : '미확인' })),
    recommendation_json: analysis.recommendation || { 법령: [], 판례: [], 유사사례: [] },
    timeline_json: (analysis.timeline || []).map((item) => ({ 날짜: item.date, 내용: item.text })),
    cluster_result_json: analysis.clusterResult || [],
    estimated_time: analysis.estimatedTime || null,
  };
}

function normalizeCoreConsultation(row) {
  return {
    coreId: row.id,
    coreUserId: row.userId,
    title: row.title,
    memo: row.inputText || '',
    opponentName: row.opponentName || '',
    coreStatus: row.status,
    createdAt: row.createdAt,
    updatedAt: row.updatedAt,
    coreAttachments: row.attachments || [],
  };
}

export async function ensureCoreUser(user) {
  const users = await requestCoreJson('/api/users');
  const existing = users.find((item) => item.email === user.email);
  if (existing) return existing;
  return requestCoreJson('/api/users', {
    method: 'POST',
    body: JSON.stringify({
      name: user.name || user.email || '상담원',
      role: toCoreRole(user.role),
      email: user.email || `local-${Date.now()}@example.local`,
    }),
  });
}

export async function createCoreConsultation({ currentUser, consultation }) {
  const coreUser = await ensureCoreUser(currentUser || { name: '상담원', role: 'counselor', email: 'local-counselor@example.local' });
  const created = await requestCoreJson('/api/consultations', {
    method: 'POST',
    body: JSON.stringify(toCoreConsultationPayload({ userId: coreUser.id, consultation })),
  });
  return normalizeCoreConsultation(created);
}

export function fetchCoreConsultations() {
  return requestCoreJson('/api/consultations');
}

export function fetchCoreUsers() {
  return requestCoreJson('/api/users');
}

export function checkCoreApiStatus() {
  return Promise.all([fetchCoreUsers(), fetchCoreConsultations()]).then(([users, consultations]) => ({
    users,
    consultations,
    userCount: users.length,
    consultationCount: consultations.length,
  }));
}

export async function deleteCoreConsultation(coreId) {
  if (!coreId) return null;
  return requestCoreJson(`/api/consultations/${coreId}`, { method: 'DELETE' });
}

export async function updateCoreConsultation(coreId, changes) {
  if (!coreId) return null;
  return requestCoreJson(`/api/consultations/${coreId}`, {
    method: 'PUT',
    body: JSON.stringify(changes),
  });
}

export function updateCoreConsultationStatus(coreId, status) {
  return updateCoreConsultation(coreId, { status });
}

export async function createCoreAnalysis({ consultation, analysis }) {
  if (!consultation?.coreId) return null;
  return requestCoreJson(`/api/consultations/${consultation.coreId}/analyses`, {
    method: 'POST',
    body: JSON.stringify(toCoreAnalysisPayload(analysis)),
  });
}

// core-api가 서버 간(backend-to-backend)으로 ai-api의 /consult/analyze를 실행하고,
// 그 결과를 ai_analysis 테이블에 저장까지 마친 뒤 돌려주는 진입점.
// (예전에는 프론트가 ai-api를 직접 호출했지만, 이제 core-api가 오케스트레이션을 담당함)
export async function triggerCoreAnalysis(consultation) {
  if (!consultation?.coreId) {
    throw new Error('Core API에 동기화되지 않은 상담입니다.');
  }
  return requestCoreJson(`/api/consultations/${consultation.coreId}/analyze`, { method: 'POST' });
}

const CORE_ELIGIBILITY_LABEL = {
  대상: '구조 가능',
  비대상: '부적합',
  판단보류: '보류',
};

// ai-api relief_review_checklist(4대 평가기준 객체)를 화면의 고정 4개 체크리스트 항목으로 재구성합니다.
// 라벨 문자열은 workflows.jsx의 로컬 체크리스트/토글 로직과 그대로 맞춰야 함(레이블로 매칭하는 코드가 있음).
function mapCoreChecklist(relief = {}) {
  const eligibilityResult = relief.eligibility || {};
  return [
    { label: '법률구조 대상 여부 확인', checked: Boolean(eligibilityResult.eligible) },
    { label: '법률구조 대상자 증빙서류 제출 여부 확인', checked: eligibilityResult.evidence_status === '충족' },
    { label: '승소 가능성 기초자료 확인', checked: Boolean(relief.winnability) },
    { label: '추가자료 요청 필요 여부 확인', checked: Boolean(relief.appropriateness) },
  ];
}

// core-api에 저장된 AiAnalysisResponse(=/consult/analyze 결과가 반영된 형태)를 프론트 내부에서 쓰는
// analysis 객체 모양(camelCase)으로 옮겨 담습니다. mapContractAnalysisResponse(legalAidApi.js, 구 /analysis
// 계약용)와 같은 출력 형태를 만들어서, 이 함수를 호출하는 workflows.jsx의 나머지 병합 로직은 그대로 재사용합니다.
// 주의: AiAnalysisResponse는 @JsonNaming(SnakeCaseStrategy)라서 실제 JSON 키는 case_type/urgency_level/
// extracted_json처럼 snake_case로 옴 — fetch가 자동으로 camelCase 변환을 해주지 않으므로 여기서 snake_case
// 키를 그대로 읽어야 함 (eligibility/summary처럼 단어가 하나뿐인 필드는 우연히 안 틀림).
// timeline은 일부러 포함하지 않습니다 — /consult/analyze 응답엔 타임라인 데이터가 없어서, 빈 배열을 반환하면
// 호출부의 스프레드(...mapped)가 기존 로컬 타임라인을 지워버리기 때문입니다.
export function mapCoreAnalysisResponse(coreAnalysis = {}) {
  const caseAnalysis = coreAnalysis.extracted_json || {};
  const relief = coreAnalysis.checklist_json || {};
  const missingItems = Array.isArray(coreAnalysis.missing_info_json) ? coreAnalysis.missing_info_json : [];
  const topCase = caseAnalysis.case_list?.[0] || {};
  return {
    summary: coreAnalysis.summary || '',
    caseType: coreAnalysis.case_type || '미분류',
    caseTypeReason: topCase.case_type_reason || '',
    urgency: coreAnalysis.urgency_level || '하',
    emergencyRatio: typeof caseAnalysis.case_emergency_ratio === 'number' ? caseAnalysis.case_emergency_ratio : null,
    eligibility: CORE_ELIGIBILITY_LABEL[coreAnalysis.eligibility] || '검토 필요',
    missingInfo: missingItems.map((item) => item?.item || item?.reason || '').filter(Boolean),
    checklist: mapCoreChecklist(relief),
    extractedJson: caseAnalysis,
  };
}

export { CORE_API_BASE_URL };
