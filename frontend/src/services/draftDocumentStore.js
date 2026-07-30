import { readStorage, storageKeys, writeStorage } from './storage.js';

function snapshotKey(snapshot = {}) {
  if (snapshot.documentId) return `doc:${snapshot.documentId}`;
  if (snapshot.localKey) return `local:${snapshot.localKey}`;
  return `case:${snapshot.consultationId || ''}:${snapshot.caseNo || ''}:${snapshot.formName || ''}`;
}

function normalizeFormName(document = {}) {
  return document.requested_form_name
    || document.requestedFormName
    || document.form_name
    || document.formName
    || '';
}

function readSnapshots() {
  return readStorage(storageKeys.documentDraftSnapshots, []);
}

function writeSnapshots(items) {
  writeStorage(storageKeys.documentDraftSnapshots, items);
  return items;
}

export function rememberDraftDocumentSnapshot({ consultation, document, draftContent, draftFilePath, downloadFileName }) {
  const nextSnapshot = {
    key: snapshotKey({
      documentId: document?.documentId || document?.document_id || '',
      localKey: document?.localKey || document?.local_key || '',
      consultationId: document?.consultationId || document?.consultation_id || consultation?.coreId || consultation?.id || '',
      caseNo: consultation?.caseNo || '',
      formName: normalizeFormName(document),
    }),
    documentId: document?.documentId || document?.document_id || '',
    localKey: document?.localKey || document?.local_key || '',
    consultationId: document?.consultationId || document?.consultation_id || consultation?.coreId || consultation?.id || '',
    caseNo: consultation?.caseNo || '',
    formName: normalizeFormName(document),
    draftContent: draftContent || document?.draftContent || document?.draft_content || '',
    draftFilePath: draftFilePath || document?.draftFilePath || document?.draft_file_path || '',
    downloadFileName: downloadFileName || document?.downloadFileName || document?.download_file_name || '',
    updatedAt: new Date().toISOString(),
  };

  const snapshots = readSnapshots();
  return writeSnapshots([nextSnapshot, ...snapshots.filter((item) => item.key !== nextSnapshot.key)]);
}

// hydrateDraftDocument 내부에서만 쓰여 더 이상 export하지 않습니다(외부 import 없음).
function findDraftDocumentSnapshot(document = {}, context = {}) {
  const snapshots = readSnapshots();
  const directKey = snapshotKey({
    documentId: document.documentId || document.document_id || '',
    localKey: document.localKey || document.local_key || '',
    consultationId: document.consultationId || document.consultation_id || context.consultationId || '',
    caseNo: context.caseNo || '',
    formName: normalizeFormName(document),
  });
  const direct = snapshots.find((item) => item.key === directKey);
  if (direct) return direct;

  const consultationId = document.consultationId || document.consultation_id || context.consultationId || '';
  const caseNo = context.caseNo || '';
  const formName = normalizeFormName(document);
  return snapshots.find((item) => (
    String(item.consultationId || '') === String(consultationId || '')
    && String(item.caseNo || '') === String(caseNo || '')
    && String(item.formName || '') === String(formName || '')
  )) || null;
}

// ── 서식 추천 결과 캐시 ──
//
// 실시간 상담 분석 화면과 서식 생성 화면이 각각 recommendCoreForms를 부릅니다.
// 그래서 분석 화면에서 추천을 본 뒤 '초안 만들기'로 넘어가면, 같은 상담·같은 분석인데도
// 서식 화면이 처음부터 다시 추천을 돌렸습니다(ai-api 임베딩 검색 + GPT 재랭킹이라 몇 초 걸리고
// 결과가 미묘하게 달라질 수도 있습니다).
//
// 분석 id가 같으면 추천 결과도 같으므로 한 번 받은 것을 재사용합니다.
// 분석을 다시 돌리면 analysisId가 바뀌어 자연히 새로 받습니다.
const formRecommendationCache = new Map();

function recommendationKey(consultationId, analysisId) {
  return `${consultationId}:${analysisId}`;
}

export function readCachedFormRecommendations(consultationId, analysisId) {
  if (!consultationId || !analysisId) return null;
  return formRecommendationCache.get(recommendationKey(consultationId, analysisId)) || null;
}

export function cacheFormRecommendations(consultationId, analysisId, recommendations) {
  if (!consultationId || !analysisId || !Array.isArray(recommendations)) return;
  formRecommendationCache.set(recommendationKey(consultationId, analysisId), recommendations);
}

export function hydrateDraftDocument(document = {}, context = {}) {
  const snapshot = findDraftDocumentSnapshot(document, context);
  if (!snapshot) return document;

  return {
    ...document,
    draft_content: document.draft_content || snapshot.draftContent || '',
    draft_file_path: document.draft_file_path || snapshot.draftFilePath || '',
    download_file_name: document.download_file_name || snapshot.downloadFileName || '',
  };
}
