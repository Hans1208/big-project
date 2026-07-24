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

function toCoreConsultationPayload({ userId, consultation }) {
  return {
    userId,
    title: consultation.title || consultation.caseNo || '상담 제목 미입력',
    inputText: consultation.memo || consultation.title || '',
    opponentName: consultation.opponentName || consultation.name || '',
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

export { CORE_API_BASE_URL };
