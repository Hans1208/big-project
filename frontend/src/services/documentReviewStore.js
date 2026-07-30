import { readStorage, storageKeys, writeStorage } from './storage.js';

const REVIEWABLE_STATUSES = new Set(['SUBMITTED_FOR_REVIEW']);

function documentKey(document) {
  return document.local_key || document.document_id || document.documentId;
}

function sameDocument(left, right) {
  return documentKey(left) === documentKey(right);
}

function readQueue() {
  return readStorage(storageKeys.documentReviewQueue, []);
}

function writeQueue(documents) {
  writeStorage(storageKeys.documentReviewQueue, documents);
  return documents;
}

export function readSubmittedLocalDocumentReviews() {
  return readQueue().filter((document) => REVIEWABLE_STATUSES.has(document.status));
}

export function saveLocalDocumentReviewRequest({ consultation, document }) {
  const submitted = {
    local_key: document.local_key || document.document_id || `local-doc-${Date.now()}`,
    document_id: document.document_id || document.documentId || document.local_key || `local-doc-${Date.now()}`,
    consultation_id: document.consultation_id || document.consultationId || consultation?.id || '',
    caseNo: consultation?.caseNo || '',
    title: consultation?.title || '',
    counselor: consultation?.counselor || null,
    form_name: document.form_name || document.formName || '선택 서식',
    requested_form_name: document.requested_form_name || document.requestedFormName || '',
    draft_file_path: document.draft_file_path || document.draftFilePath || '',
    download_file_name: document.download_file_name || document.downloadFileName || '',
    draft_content: document.draft_content || document.draftContent || '',
    status: 'SUBMITTED_FOR_REVIEW',
    source: document.source || 'ai-api-local',
    submitted_at: new Date().toISOString(),
    review_note: '',
    requested_materials: [],
  };
  const nextQueue = [submitted, ...readQueue().filter((item) => !sameDocument(item, submitted))];
  writeQueue(nextQueue);
  return submitted;
}

export function updateLocalDocumentReview(documentKeyValue, changes) {
  const nextQueue = readQueue().map((document) => (
    documentKey(document) === documentKeyValue
      ? { ...document, ...changes, reviewed_at: new Date().toISOString() }
      : document
  ));
  writeQueue(nextQueue);
  return nextQueue.find((document) => documentKey(document) === documentKeyValue) || null;
}

// 브라우저 로컬 큐(ai-api-local/text-local/client-hwpx)에 남은 항목을 완전히 지웁니다.
export function removeLocalDocumentReview(documentKeyValue) {
  const nextQueue = readQueue().filter((document) => documentKey(document) !== documentKeyValue);
  writeQueue(nextQueue);
  return nextQueue;
}

// 코어 API에서 내려오는 항목은 삭제 API가 없어 "숨김" 처리로 화면에서만 치웁니다.
// (백엔드 상태는 그대로 SUBMITTED_FOR_REVIEW로 남지만, 이 목록 조회 시 걸러냅니다.)
function readDismissedKeys() {
  return readStorage(storageKeys.dismissedDocumentReviews, []);
}

export function dismissDocumentReview(reviewKey) {
  if (!reviewKey) return readDismissedKeys();
  const current = readDismissedKeys();
  if (current.includes(reviewKey)) return current;
  const next = [...current, reviewKey];
  writeStorage(storageKeys.dismissedDocumentReviews, next);
  return next;
}

export function isDocumentReviewDismissed(reviewKey) {
  return readDismissedKeys().includes(reviewKey);
}

// 변호사가 서식 초안을 직접 고친 내용입니다. core-api에서 온 문서는 실제 HWPX 파일을 다시
// 만들어주는 API가 없어 서버 원본을 덮어쓸 수는 없지만, 화면에서 보여줄 '변호사 수정본'은
// 이 브라우저에 남겨 상담원이 검토 결과를 열 때 함께 볼 수 있게 합니다.
function readLawyerDraftEdits() {
  return readStorage(storageKeys.lawyerDraftEdits, {});
}

export function saveLawyerDraftEdit(reviewKey, content) {
  if (!reviewKey) return null;
  const store = readLawyerDraftEdits();
  const entry = { content, updatedAt: new Date().toISOString() };
  writeStorage(storageKeys.lawyerDraftEdits, { ...store, [reviewKey]: entry });
  return entry;
}

export function readLawyerDraftEdit(reviewKey) {
  if (!reviewKey) return null;
  return readLawyerDraftEdits()[reviewKey] || null;
}
