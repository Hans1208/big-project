import React, { useEffect, useRef, useState } from 'react';
import {
  ShieldCheck, ClipboardList, ChevronDown, ChevronRight, FileText, Info, Search, Check, FileAudio2, Mic, PhoneCall, Radio, Headphones,
  FileSearch, Paperclip, EyeOff, BadgeCheck, Scale, ListChecks, Sparkles, Clock, Inbox,
  FolderOpen, MessageSquareText, CheckCircle2, XCircle, UploadCloud, Trash2, Star, Send, Plus, AlertTriangle,
  Bell, BellOff, User, Lock, TrendingUp, Gavel, Award, BookOpen, Download,
} from 'lucide-react';
import { today } from '../constants.jsx';
import { validatePassword, PASSWORD_RULE_TEXT } from './auth.jsx';
import { formatDateTimeLabel } from '../utils/date.js';
import { createAttachmentMetadata, generateDraftText, recommendTemplates, searchReferenceCandidates, validateAnalysisResult } from '../services/legalAidApi.js';
import { appendAuditLog, getFavoriteTemplates, readStorage, storageKeys, toggleFavoriteTemplate, writeStorage } from '../services/storage.js';
import {
  approveCoreDocument,
  buildCoreDocumentDownloadUrl,
  changeCorePassword,
  coreAuthHeader,
  createCoreAnalysis,
  createCoreConsultation,
  deleteCoreAttachment,
  deleteUnregisteredCoreAttachment,
  fetchCoreDocuments,
  findActiveCoreAnalysisJob,
  generateCoreDraft,
  getCoreAnalysisJob,
  recommendCoreForms,
  registerCoreAttachment,
  submitCoreAnalysisForReview,
  submitCoreDocumentForReview,
  triggerCoreAnalysis,
  isCoreConnectionError,
  mapCoreAnalysisResponse,
  timelineEmptyMessage,
  waitForCoreAnalysisJob,
} from '../services/coreApiClientV2.js';
import { cacheFormRecommendations, hydrateDraftDocument, readCachedFormRecommendations, rememberDraftDocumentSnapshot } from '../services/draftDocumentStore.js';
import { readLawyerDraftEdit, saveLawyerDraftEdit } from '../services/documentReviewStore.js';
import { createClientHwpxDraft } from '../services/clientHwpxGenerator.js';
import { isHwpxTemplateAlias, resolveHwpxTemplateName } from '../services/formTemplateResolver.js';
import { uploadFileToS3, S3UploadUnavailableError } from '../services/s3UploadClient.js';
import { transcribeAudio } from '../services/sttApiClient.js';
import { createRealtimeAudioStream, fetchAvailableAudioCalls } from '../services/realtimeAudioStream.js';
import { caseCategories, isKnownCaseType, legalTemplateSeed } from '../data/domain.js';
import { CollapsibleSection, HitlConfirmModal, InlineEmptyNotice, WorkPageHeader, friendlyErrorMessage } from '../components/common.jsx';
import { useAsyncAction } from '../components/loading.jsx';
import { useConfirm, useToast } from '../components/feedback.jsx';

// 경과 초를 "1:05" 모양으로. 1분이 넘어가면 초만 보여줘서는 얼마나 지났는지 감이 안 옵니다.
function formatElapsed(totalSeconds) {
  if (!totalSeconds) return '';
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return minutes ? `${minutes}:${String(seconds).padStart(2, '0')}` : `${seconds}초`;
}

// core-api 연결 자체가 안 되면(서버 꺼짐 등) 로컬 목업 결과로 자연스럽게 대체해,
// 데모/개발 도중에도 화면이 끊기지 않도록 합니다.
//
// 다만 "분석이 실패했다"는 목업으로 덮지 않고 그대로 올립니다. 예전에는 모든 실패를
// 목업으로 바꿔서, AI 분석이 실패해도 화면에는 그럴듯한 결과가 떴습니다. 상담원은 그걸
// 실제 분석 결과로 믿고 저장하게 됩니다.
async function fetchAnalysisWithFallback(selectedCase, options = {}) {
  const localFallback = buildAnalysisResult(selectedCase);
  try {
    const coreResult = await triggerCoreAnalysis(selectedCase, options);
    // 백엔드가 아직 채워주지 않는 항목(모달리티 요약, 파일별 추출 상태, STT 마스킹 미리보기 등)은
    // 로컬 목업 값을 그대로 이어서 쓰고, 실제 응답이 담긴 핵심 분석 필드만 덮어씁니다.
    return mergeContractAnalysisResponse(localFallback, coreResult);
  } catch (error) {
    if (isCoreConnectionError(error)) return localFallback;
    throw error;
  }
}

// 분석 실행을 화면 밖(App)에서 돌릴 수 있게 떼어낸 입구입니다.
//
// 분석은 40~70초 걸립니다. 이걸 AnalysisWorkbench 안에서 await하면 상담원이 다른 메뉴로
// 옮기는 순간 컴포넌트가 언마운트되면서 기다리던 것도 같이 사라집니다. 서버(analysis_job)는
// 계속 돌지만 결과를 받을 주체가 없어 그대로 버려집니다.
//
// App이 이 함수를 호출하면 화면을 옮겨 다녀도 끝까지 진행되고, 끝났을 때 알림을 띄울 수
// 있습니다. 화면에 그릴 analysis와 상담에 반영할 patch를 함께 돌려줍니다.
export async function runConsultationAnalysis(consultation, options = {}) {
  const analysis = await fetchAnalysisWithFallback(consultation, options);

  // 분석 결과 자체를 상담에 실어 보관합니다 — 화면 상태에만 두면 페이지를 옮길 때 사라집니다.
  // 서버 저장과는 무관합니다: ai_analysis 행은 상담원이 "분석 내용 저장"을 눌러야 생깁니다.
  const patch = { analysis };
  if (analysis.analysisId && analysis.analysisId !== consultation.coreAnalysisId) {
    patch.coreAnalysisId = analysis.analysisId;
  }

  // 통화에서 확인된 상담자 이름을 AI가 채웁니다. 전화를 받자마자 상담이 만들어지므로
  // 시작 시점에는 이름을 모르고, 분석이 끝나야 알 수 있습니다.
  //
  // 상담원이 직접 입력·수정한 이름은 덮어쓰지 않습니다. Whisper가 '이도영'을 '이도형'으로
  // 듣는 일이 있는데, 사람이 확인해 고쳐둔 값을 기계가 되돌리면 안 됩니다.
  const aiName = pickClientName(analysis);
  if (aiName && !consultation.name && consultation.nameSource !== 'counselor') {
    patch.name = aiName;
    patch.nameSource = 'ai';
  }
  return { analysis, patch };
}

// 저장된 분석(core-api 응답)을 화면이 쓸 수 있는 모양으로 되살립니다.
//
// 분석을 방금 돌린 경로(fetchAnalysisWithFallback)와 같은 병합을 거치게 해서, 새로고침 후
// 복원한 분석도 같은 모양이 되게 합니다. 이 병합을 건너뛰면 화면이 그리는 값 중 계약에 없는
// 것들(modalities, extractionDetail, sttPreview, verification)이 undefined로 남아
// `analysis.modalities.map(...)`에서 터집니다.
//
// buildAnalysisResult는 이 파일 내부 구현이라 밖으로 내보내지 않고, 복원용 입구만 엽니다.
export function hydrateAnalysisForDisplay(contractResult, consultation) {
  return mergeContractAnalysisResponse(buildAnalysisResult(consultation || {}), contractResult);
}

function mergeContractAnalysisResponse(baseAnalysis, contractResult, extra = {}) {
  const mapped = mapCoreAnalysisResponse(contractResult);
  // 긴급도 등급과 점수를 항상 짝이 맞게 재구성합니다.
  // - 백엔드가 사건별 점수(case_emergency_ratio)를 주면 그 값을 기준으로 등급을 정합니다(실제 AI).
  // - 점수 없이 등급만 오면(계약 mock은 등급이 고정이라 사건 구분이 안 됨) buildAnalysisResult가
  //   상담 내용으로 계산한 사건별 등급·점수를 그대로 신뢰합니다.
  const backendRatio = typeof mapped.emergencyRatio === 'number' ? mapped.emergencyRatio : null;
  const level = backendRatio != null ? levelFromRatio(backendRatio) : (baseAnalysis.urgency || '하');
  const ratio = backendRatio != null ? backendRatio : (baseAnalysis.emergency?.ratio ?? 0.15);
  return {
    ...baseAnalysis,
    ...mapped,
    urgency: level,
    emergency: { level, ratio, reason: emergencyReason(level) },
    ...extra,
    extractedJson: {
      ...(baseAnalysis.extractedJson || {}),
      ...(mapped.extractedJson || {}),
      aiAnalysisResponse: contractResult,
      ...(extra.extractedJson || {}),
    },
  };
}

// 코치 피드백: "줄글이 아닌 개요 형식의 짧게 요약". AI 요약이 문장 여러 개로 이어진 줄글로
// 오더라도, 문장 단위(마침표·줄바꿈)로 쪼개 개요(bullet) 목록으로 보여줍니다.
function splitSummaryIntoBullets(summaryText = '') {
  // 문장으로 끊어 쓴 요약은 마침표 기준으로, "사건 유형: 이혼 / 긴급도: 중"처럼 슬래시로
  // 항목을 나열한 요약(core-api 응답 형식)은 슬래시 기준으로 쪼갭니다.
  return summaryText
    .split(/(?<=[.!?다요])\s+|\n+|\s+\/\s+/)
    .map((sentence) => sentence.trim())
    .filter(Boolean);
}

function SummaryBulletList({ text, emptyText = '요약 없음', maxItems }) {
  const bullets = splitSummaryIntoBullets(text);
  if (!bullets.length) return <p>{emptyText}</p>;
  const visibleBullets = maxItems ? bullets.slice(0, maxItems) : bullets;
  // 문장이 하나뿐이면 목록으로 쪼갤 이유가 없어(오히려 산만해 보임) 마커 없는 한 줄로 둡니다.
  const isSingleLine = visibleBullets.length === 1;
  return (
    <ul className={`summaryBulletList${isSingleLine ? ' singleLine' : ''}`}>
      {visibleBullets.map((sentence, index) => <li key={`${index}-${sentence.slice(0, 12)}`}>{sentence}</li>)}
    </ul>
  );
}

function normalizeMissingInfoItems(items = []) {
  return items.map((item) => {
    if (typeof item === 'string') return item;
    if (item?.item) return item.item;
    if (item?.name) return item.name;
    if (item?.reason) return item.reason;
    return String(item);
  }).filter(Boolean);
}

function markAiLinkedSection(analysis, sectionKey) {
  return {
    ...analysis,
    aiLinked: {
      ...(analysis.aiLinked || {}),
      [sectionKey]: {
        updatedAt: new Date().toISOString(),
      },
    },
  };
}

// 긴급도 등급별 점수 대역. 같은 등급 안에서도 사건마다 다른 값이 나오도록 '고정값'이 아니라 '구간'으로 둡니다.
const URGENCY_BAND = { 상: [0.66, 0.97], 중: [0.36, 0.65], 하: [0.05, 0.35] };

// 긴급 신호 키워드. 상담 내용에 있을수록 점수가 올라갑니다.
// (백엔드 ai-api의 긴급도 판단 기준 프롬프트와 같은 맥락: 생명·신체 위험, 시효·집행 임박 등)
const HIGH_URGENCY_SIGNALS = ['강제집행', '소멸시효', '시효', '임박', '즉시', '당장', '폭행', '협박', '생명', '위독', '위험', '구속', '체포', '경매', '압류', '가압류', '퇴거', '명도', '자살', '실종'];
const MID_URGENCY_SIGNALS = ['소송', '기일', '재판', '조정', '최고', '내용증명', '합의', '미지급', '체불', '연체', '독촉', '이혼', '양육비', '상속', '기한'];

// 긴급도 등급 → 근거 문장. 등급 하나에서만 나오게 해 등급과 근거가 어긋나지 않게 합니다.
function emergencyReason(level) {
  return level === '상'
    ? '즉시 대응이 필요한 정황(기한 임박·금전 피해 등)으로 보입니다.'
    : level === '중'
      ? '수일~수주 내 대응이 필요한 사안으로 보입니다.'
      : '특별한 시한 압박은 낮은 것으로 보입니다.';
}

// 0~1 점수를 등급으로 변환.
function levelFromRatio(ratio) {
  return ratio >= URGENCY_BAND.상[0] ? '상' : ratio >= URGENCY_BAND.중[0] ? '중' : '하';
}

// 점수가 등급 대역을 벗어나면 그 대역 안으로 보정합니다. (백엔드가 등급만 줄 때 등급-점수 일관성 유지)
function fitRatioToLevel(ratio, level) {
  const band = URGENCY_BAND[level] || URGENCY_BAND.하;
  return Number(Math.min(band[1], Math.max(band[0], ratio)).toFixed(2));
}

// 긴급도(등급/점수/근거)를 상담 내용과 첨부자료의 여러 신호를 종합해 계산합니다.
// 등급별 고정 점수가 아니라, 신호를 가중합한 연속 점수를 내고 그 점수로 등급을 정합니다.
// → 같은 '상'이라도 사건마다 점수가 다르고, 사건 내용이 다르면 등급도 갈립니다.
// (백엔드 AI가 case_emergency_ratio를 주면 그 값을 우선 쓰고, 이 로컬 계산은 백엔드가 없을 때만 씁니다.)
function computeCaseEmergency(selectedCase) {
  const text = `${selectedCase?.title || ''} ${selectedCase?.memo || ''}`;
  const attachments = selectedCase?.attachments || [];
  const hasMultimodalEvidence = summarizeAttachmentModalities(attachments).some((item) => item.count > 0);

  let score = 0.12; // 단순 문의 수준의 기본선
  HIGH_URGENCY_SIGNALS.forEach((keyword) => { if (text.includes(keyword)) score += 0.17; });
  MID_URGENCY_SIGNALS.forEach((keyword) => { if (text.includes(keyword)) score += 0.08; });
  // 금액 규모: 자릿수가 클수록(만원→억) 가중
  const amounts = text.match(/\d[\d,]{2,}/g);
  if (amounts) {
    const maxDigits = Math.max(...amounts.map((value) => value.replace(/\D/g, '').length));
    score += Math.min(0.2, maxDigits * 0.03);
  }
  // 근거 자료가 많을수록 사안이 구체적이라고 보고 미세 가중
  if (hasMultimodalEvidence) score += 0.08;
  score += Math.min(0.1, attachments.length * 0.03);
  score += Math.min(0.06, (selectedCase?.memo || '').length / 2000);

  // 같은 키워드 조합이라도 사건마다 점수가 똑같이 겹쳐 보이지 않도록 사건 식별자 기반의 작은 흔들림을 더합니다.
  // caseNo/id로 만든 결정론적 값이라 새로고침해도 점수가 바뀌지 않습니다.
  const seed = String(selectedCase?.caseNo || selectedCase?.id || text).split('').reduce((sum, char) => sum + char.charCodeAt(0), 0);
  score += ((seed % 7) - 3) * 0.01; // -0.03 ~ +0.03

  const ratio = Number(Math.max(0.05, Math.min(0.97, score)).toFixed(2));
  const level = levelFromRatio(ratio);
  return { level, ratio, reason: emergencyReason(level) };
}

// 상담 등록 단계에서 확인한 대상 유형·증빙 제출 여부로 구조대상 여부를 판정합니다.
// 대상 후보이면서 증빙까지 제출됐으면 '구조 가능', 대상 후보인데 증빙 미제출이면 '검토 필요',
// 애초에 대상 후보가 아니면 '부적합'으로 봅니다.
function resolveEligibilityFromCase(selectedCase, fallbackCheck) {
  const eligibilityCheck = selectedCase?.eligibilityCheck || fallbackCheck || null;
  const isTargetCandidate = Boolean(eligibilityCheck?.isTargetCandidate);
  const evidenceSubmitted = Boolean(eligibilityCheck?.evidenceSubmitted);
  const eligibility = isTargetCandidate ? (evidenceSubmitted ? '구조 가능' : '검토 필요') : '부적합';
  return { eligibilityCheck, isTargetCandidate, evidenceSubmitted, eligibility };
}

function buildAiResultSummary(kind, result) {
  if (!result) return null;
  if (kind === 'eligibility') {
    return {
      title: '무료 법률구조 대상 확인 결과',
      description: '무료 법률구조 대상, 증빙 제출 여부, 긴급도 등급을 상담 내용에 반영했습니다.',
      metrics: [
        { label: '무료 법률구조 대상', value: result.eligibility || '검토 필요' },
        { label: '증빙 제출', value: result.eligibilityCheck?.evidenceSubmitted ? '제출 완료' : '미제출' },
        { label: '긴급도 등급', value: result.urgency ? `${result.urgency} (${Math.round((result.emergency?.ratio || 0) * 100)}%)` : '미확인' },
      ],
      items: [
        `무료 법률구조 대상: ${result.eligibility || '검토 필요'}`,
        `증빙서류: ${result.eligibilityCheck?.evidenceSubmitted ? '제출 확인됨' : `미제출${result.eligibilityCheck?.requiredEvidence ? ` (${result.eligibilityCheck.requiredEvidence})` : ''}`}`,
        `긴급도 근거: ${result.emergency?.reason || '근거 없음'}`,
      ],
    };
  }
  return {
    title: '누락자료 점검 결과',
    description: '보완이 필요한 자료를 찾아 아래 누락 자료 목록에 추가했습니다.',
    metrics: [
      { label: '누락자료', value: `${result.missingInfo?.length || 0}건` },
      { label: '제출 완료', value: `${Object.values(result.evidenceStatus || {}).filter((value) => value === 'submitted').length}건` },
      { label: '체크리스트', value: `${result.checklist?.filter((item) => item.checked).length || 0}/${result.checklist?.length || 0}` },
    ],
    items: (result.missingInfo || []).slice(0, 6).map((item) => `보완 필요: ${item}`),
  };
}

// 구조대상 확인·누락자료 점검은 '분석 시작'에서 받은 결과를 그대로 씁니다.
//
// /consult/analyze는 사건분석·구조대상·누락자료를 항상 한 번에 계산해 돌려주므로, 버튼마다
// 다시 호출하면 같은 것을 세 번 계산하게 됩니다. 시간(매회 40~70초)과 API 비용도 문제지만
// 진짜 이유는 따로 있습니다: LLM은 같은 입력에도 응답이 흔들려서, 세 번 부르면 세 개의 서로
// 다른 판단이 나옵니다. 그러면 한 화면에 사건유형은 1회차 결과, 구조대상은 2회차 결과가
// 섞여 들어가 상담 기록이 앞뒤가 안 맞게 됩니다.
//
// 아직 분석 전이라 쓸 결과가 없으면(상담원이 이 버튼부터 누른 경우) 그때만 새로 돌립니다.
// aiAnalysisResponse는 mergeContractAnalysisResponse가 실제 백엔드 응답을 받았을 때만
// 채우므로, 백엔드가 꺼져 로컬 목업으로 돌아간 분석을 실제 결과로 착각할 일은 없습니다.
async function resolveAnalysisResponse(selectedCase, analysis, options = {}) {
  const alreadyAnalyzed = analysis?.extractedJson?.aiAnalysisResponse;
  if (alreadyAnalyzed) return alreadyAnalyzed;
  return triggerCoreAnalysis(selectedCase, options);
}

async function requestEligibilityCandidate(selectedCase, analysis, options = {}) {
  // 상담 등록 데이터를 근거로 대상여부·증빙·긴급도를 확정 계산합니다.
  // (백엔드 mock이 이 값들을 채워주지 않아도 버튼 한 번으로 실제 반영되도록 로컬 계산을 기본값으로 씁니다)
  const emergency = computeCaseEmergency(selectedCase);
  const { eligibilityCheck, isTargetCandidate, evidenceSubmitted, eligibility } = resolveEligibilityFromCase(selectedCase, analysis.eligibilityCheck);

  let mapped = {};
  let response = null;
  try {
    // /consult/analyze는 단일화된 파이프라인이라 부분 출력만 요청하는 개념이 없음 — 항상 전체를 반환받음.
    // 그래서 분석 시작 때 받아둔 응답을 재사용합니다(resolveAnalysisResponse 주석 참고).
    response = await resolveAnalysisResponse(selectedCase, analysis, options);
    mapped = mapCoreAnalysisResponse(response);
  } catch (error) {
    // 백엔드가 꺼져 있으면 위에서 계산한 로컬 값만으로 진행합니다.
    // 분석이 실제로 실패한 경우는 감추지 않고 알립니다(fetchAnalysisWithFallback와 같은 이유).
    if (!isCoreConnectionError(error)) throw error;
  }

  // 긴급도: 백엔드가 사건별 점수(case_emergency_ratio)를 주면 그 값을 최우선으로 씁니다.
  // 점수는 없고 등급만 오면, 사건별 로컬 점수를 그 등급 대역 안으로 보정해 등급-점수를 일관되게 맞춥니다.
  const backendRatio = typeof mapped.emergencyRatio === 'number' ? mapped.emergencyRatio : null;
  const urgency = backendRatio != null ? levelFromRatio(backendRatio) : (mapped.urgency || emergency.level);
  const urgencyRatio = backendRatio != null ? backendRatio : fitRatioToLevel(emergency.ratio, urgency);
  // 대상/증빙 관련 체크리스트 항목은 방금 확정한 값에 맞춰 자동으로 채웁니다.
  const baseChecklist = mapped.checklist?.length ? mapped.checklist : analysis.checklist;
  const checklist = baseChecklist.map((item) => {
    if (item.label.includes('대상 여부')) return { ...item, checked: Boolean(eligibilityCheck) };
    if (item.label.includes('증빙')) return { ...item, checked: !isTargetCandidate || evidenceSubmitted };
    return item;
  });

  return markAiLinkedSection({
    ...analysis,
    eligibility,
    eligibilityCheck,
    urgency,
    emergency: { level: urgency, ratio: urgencyRatio, reason: emergencyReason(urgency) },
    checklist,
    missingInfo: Array.from(new Set([...(analysis.missingInfo || []), ...normalizeMissingInfoItems(mapped.missingInfo || [])])),
    extractedJson: {
      ...(analysis.extractedJson || {}),
      aiEligibilityResponse: response,
    },
  }, 'eligibility');
}

// 백엔드가 없을 때 상담 데이터만으로 '더 받아야 할 자료' 후보를 만듭니다.
function localMissingDataSuggestions(selectedCase) {
  const attachments = selectedCase?.attachments || [];
  const eligibilityCheck = selectedCase?.eligibilityCheck;
  const hasAudio = attachments.some((item) => /transcript|녹취|audio/i.test(item.category || item.name || ''));
  return [
    ...(eligibilityCheck?.isTargetCandidate && !eligibilityCheck?.evidenceSubmitted ? [`${eligibilityCheck.requiredEvidence || '대상자 증빙서류'}`] : []),
    ...(hasAudio ? [] : ['상담 녹취록']),
    '상대방 연락처·주소',
    '관련 계약서 또는 거래 증빙',
    '기존 소송·조정 이력',
  ];
}

async function requestMissingDataCandidate(selectedCase, analysis, options = {}) {
  let mapped = {};
  let response = null;
  try {
    // 분석 시작 때 받아둔 응답을 재사용합니다(resolveAnalysisResponse 주석 참고).
    response = await resolveAnalysisResponse(selectedCase, analysis, options);
    mapped = mapCoreAnalysisResponse(response);
  } catch (error) {
    // 백엔드가 꺼져 있으면 아래 로컬 제안 목록을 씁니다.
    if (!isCoreConnectionError(error)) throw error;
  }

  const suggested = normalizeMissingInfoItems(mapped.missingInfo || []);
  const additions = suggested.length ? suggested : localMissingDataSuggestions(selectedCase);
  const missingInfo = Array.from(new Set([...(analysis.missingInfo || []), ...additions]));
  // 새로 추가된 항목만 '미제출'로 초기화하고, 이미 상담원이 표시한 제출 상태는 그대로 둡니다.
  const evidenceStatus = { ...(analysis.evidenceStatus || {}) };
  missingInfo.forEach((item) => { if (!evidenceStatus[item]) evidenceStatus[item] = 'missing'; });

  // '구조대상 판정' 버튼은 체크리스트 중 '대상 여부'·'증빙' 항목을 자동으로 채웁니다(requestEligibilityCandidate).
  // 이 버튼(누락자료 점검)은 나머지 항목(승소 가능성/집행 가능성/구조 타당성/추가자료 요청 필요 여부 등
  // 대상·증빙과 무관한 모든 항목)을 점검 완료로 체크해, 두 버튼이 각각 자신이 맡은 체크리스트 항목만
  // 자동으로 채우도록 역할을 나눕니다.
  const baseChecklist = mapped.checklist?.length ? mapped.checklist : analysis.checklist;
  const checklist = baseChecklist.map((item) => (
    item.label.includes('대상 여부') || item.label.includes('증빙') ? item : { ...item, checked: true }
  ));

  return markAiLinkedSection({
    ...analysis,
    missingInfo,
    evidenceStatus,
    checklist,
    extractedJson: {
      ...(analysis.extractedJson || {}),
      aiMissingDataResponse: response,
    },
  }, 'missing');
}

function caseOptions(consultations) {
  return consultations.length ? consultations : [{ id: 'empty', caseNo: '상담 선택', title: '등록된 상담이 없습니다.' }];
}

// 서식 추천(legalTemplateSeed)과 법령·판례 검색은 소분류(caseSubtype) 단위로 데이터가 연결돼 있습니다.
// (legalTemplateSeed의 caseType 필드가 실제로는 '가사소송일반' 같은 소분류 값입니다.)
// AI 분석은 대분류(caseType)와 소분류(caseSubtype)를 따로 주므로, 소분류가 있으면 그걸 우선 쓰고
// 없거나 이 시스템이 모르는 값이면 대분류로, 그마저 없으면 상담 등록 때 고른 유형으로 내려갑니다.
export function resolveConfirmedCaseType(selectedCase) {
  const analysis = selectedCase?.analysis;
  if (isKnownCaseType(analysis?.caseSubtype)) return analysis.caseSubtype;
  if (isKnownCaseType(analysis?.caseType)) return analysis.caseType;
  return selectedCase?.type;
}

function casePickerFields(item) {
  return [
    item.caseNo,
    item.name,
    item.title,
    item.type,
    item.subtype,
    item.date,
    item.registeredTime,
  ].filter(Boolean);
}

function matchesCasePickerQuery(item, query) {
  const normalizedQuery = query.trim().toLowerCase();
  if (!normalizedQuery) return true;
  return casePickerFields(item).some((field) => String(field).toLowerCase().includes(normalizedQuery));
}

function casePickerDateLabel(item) {
  if (!item?.date) return '등록일시 미기록';
  return `${item.date}${item.registeredTime ? ` ${item.registeredTime}` : ''}`;
}

function CasePicker({ consultations, value, onChange, placeholder = '사건을 선택하세요' }) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');
  const options = caseOptions(consultations);
  const matchedSelection = options.find((item) => String(item.id) === String(value));
  const selected = matchedSelection || options[0];
  const filteredOptions = options.filter((item) => matchesCasePickerQuery(item, query));
  // matchedSelection이 없으면(예: value가 아직 존재하지 않는 사건을 가리킴) 목록의 첫 항목을
  // 화면에 마치 선택된 것처럼 보여주면 안 됩니다 — 실제로는 아무 사건도 선택되지 않은
  // 상태라 통화/메모 컨트롤이 비활성 상태로 남는데, 여기서 첫 사건 정보를 그대로 보여주면
  // 사용자는 사건이 선택된 것으로 착각하고 왜 입력이 안 되는지 알 수 없습니다.
  const hasSelectableCase = Boolean(matchedSelection) && matchedSelection.id !== 'empty';

  const selectCase = (item) => {
    if (item.id === 'empty') return;
    onChange(item.id);
    setQuery('');
    setOpen(false);
  };

  return (
    <div className="casePicker">
      <button
        className="casePickerButton"
        type="button"
        onClick={() => setOpen((current) => !current)}
        aria-expanded={open}
      >
        <span className="casePickerButtonText">
          <strong>{hasSelectableCase ? selected.caseNo : placeholder}</strong>
          <span>{hasSelectableCase ? `${selected.name || '상담자 미지정'} · ${selected.title || '상담 제목 미입력'}` : selected?.title || '등록된 상담이 없습니다.'}</span>
          {hasSelectableCase ? <small>{casePickerDateLabel(selected)}</small> : null}
        </span>
        <ChevronDown size={18} strokeWidth={2.2} aria-hidden="true" />
      </button>
      {open ? (
        <div className="casePickerPopover">
          <label className="casePickerSearch">
            <Search size={15} strokeWidth={2.2} aria-hidden="true" />
            <input
              autoFocus
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="사건번호, 이름, 제목 검색"
            />
          </label>
          <div className="casePickerList">
            {filteredOptions.length ? filteredOptions.map((item) => (
              <button
                className={String(item.id) === String(value) ? 'casePickerItem active' : 'casePickerItem'}
                type="button"
                key={item.id}
                disabled={item.id === 'empty'}
                onClick={() => selectCase(item)}
              >
                <span>
                  <strong>{item.caseNo || '사건번호 없음'}</strong>
                  <small>{item.name || '상담자 미지정'} · {item.title || '상담 제목 미입력'}</small>
                </span>
                <em>{item.id === 'empty' ? '없음' : casePickerDateLabel(item)}</em>
              </button>
            )) : (
              <p className="casePickerEmpty">검색 결과 없음</p>
            )}
          </div>
        </div>
      ) : null}
    </div>
  );
}

function normalizeChoiceOptions(options) {
  return options.map((option) => (typeof option === 'string' ? { value: option, label: option } : option));
}

function matchesChoiceQuery(option, query) {
  const normalizedQuery = query.trim().toLowerCase();
  if (!normalizedQuery) return true;
  return [option.label, option.description].filter(Boolean).some((field) => String(field).toLowerCase().includes(normalizedQuery));
}

function ChoicePicker({ options, value, onChange, placeholder = '선택하세요', disabled = false }) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');
  const normalizedOptions = normalizeChoiceOptions(options);
  const selected = normalizedOptions.find((option) => String(option.value) === String(value));
  const filteredOptions = normalizedOptions.filter((option) => matchesChoiceQuery(option, query));

  const selectOption = (option) => {
    onChange(option.value);
    setQuery('');
    setOpen(false);
  };

  return (
    <div className="choicePicker">
      <button
        className="choicePickerButton"
        type="button"
        disabled={disabled}
        onClick={() => setOpen((current) => !current)}
        aria-expanded={open}
      >
        <span className="choicePickerText">
          <strong>{selected?.label || placeholder}</strong>
          {selected?.description ? <small>{selected.description}</small> : null}
        </span>
        <ChevronDown size={18} strokeWidth={2.2} aria-hidden="true" />
      </button>
      {open && !disabled ? (
        <div className="choicePickerPopover">
          <label className="choicePickerSearch">
            <Search size={15} strokeWidth={2.2} aria-hidden="true" />
            <input
              autoFocus
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="항목 검색"
            />
          </label>
          <div className="choicePickerList">
            {filteredOptions.length ? filteredOptions.map((option) => (
              <button
                className={String(option.value) === String(value) ? 'choicePickerItem active' : 'choicePickerItem'}
                type="button"
                key={option.value}
                onClick={() => selectOption(option)}
              >
                <strong>{option.label}</strong>
                {option.description ? <small>{option.description}</small> : null}
              </button>
            )) : (
              <p className="choicePickerEmpty">검색 결과 없음</p>
            )}
          </div>
        </div>
      ) : null}
    </div>
  );
}

const legalAidApplicantTypes = [
  { key: 'none', label: '해당 없음', evidence: '대상자 증빙 없음' },
  { key: 'basicLivelihood', label: '기초생활수급자', evidence: '수급자 증명서' },
  { key: 'nearPoverty', label: '차상위계층', evidence: '차상위계층 확인서' },
  { key: 'disabled', label: '장애인', evidence: '장애인증명서 또는 복지카드' },
  { key: 'nationalMerit', label: '국가유공자', evidence: '국가유공자 확인서' },
  { key: 'crimeVictim', label: '범죄피해자', evidence: '피해사실 확인자료' },
  { key: 'domesticViolence', label: '가정폭력·성폭력 피해자', evidence: '상담확인서 또는 피해확인자료' },
  { key: 'wageArrears', label: '임금등 체불 피해근로자', evidence: '체불임금 확인자료' },
  { key: 'courtRescue', label: '법원의 소송구조 결정자', evidence: '소송구조 결정문' },
  { key: 'other', label: '기타 법률구조 대상자', evidence: '대상자 확인자료' },
];

// AI 백본 extracted_content_detail의 status 값을 사람이 읽을 수 있는 라벨로 변환합니다.
function extractionStatusLabel(status) {
  const labels = { success: '추출 성공', empty: '내용 없음', unsupported: '미지원', failed: '처리 실패' };
  return labels[status] || status;
}

function getEligibilityBadgeText(isApplicant, evidenceSubmitted) {
  if (!isApplicant) return '대상 아님';
  if (!evidenceSubmitted) return '증빙 필요';
  return '대상 확인';
}

function getEligibilityHelperText(isApplicant, evidenceSubmitted) {
  if (!isApplicant) return '법률구조 대상 유형에 해당하지 않는 것으로 표시됩니다.';
  if (!evidenceSubmitted) return '법률구조 대상자에 해당할 수 있으나 증빙서류가 아직 제출되지 않았습니다.';
  return '법률구조 대상자로 확인되었고 증빙서류 제출도 완료되었습니다.';
}

// 업로드 상태 문자열을 상태 칩 색 톤으로 매핑합니다.
function uploadStatusTone(status) {
  if (status === '업로드 완료' || status === '업로드·텍스트 변환 완료' || status === '서버 저장') return 'tone-success';
  if (status === '업로드 실패') return 'tone-danger';
  if (status === '업로드 중') return 'tone-info';
  return 'tone-warn'; // 로컬 보관 (S3 대기) 등
}

// 오른쪽 2단계 카드는 예전엔 왼쪽 문단이 말로 설명하는 내용을 그림으로 다시 보여주기만 해서
// 있으나 마나 했습니다. 지금은 '지금 여기' 표시뿐 아니라, 지금 있지 않은 단계를 눌러 바로
// 넘어갈 수 있는 작은 스텝 네비게이션으로 씁니다(상단 메뉴까지 갈 필요 없이 화면 안에서 전환).
function CounselorFlowStage({ current = 'realtime', onNavigate }) {
  // 통화를 받으면서 곧바로 진행하는 실시간 상담이 먼저이고, 문서 업로드는 통화가 끝난 뒤
  // 자료를 정리해 변호사 검토로 넘기는 후처리 단계입니다. (코치 피드백: 실시간 중심으로 순서 변경)
  const stages = [
    {
      key: 'realtime',
      icon: Radio,
      title: '실시간 상담',
      detail: '통화 시작 · 메모 · AI 분석',
    },
    {
      key: 'upload',
      icon: FileAudio2,
      title: '상담 자료 올리기',
      detail: '통화 후 자료 정리 · 변호사 검토 전달',
    },
  ];

  return (
    <section className="flowStageBanner" aria-label="상담원 업무 단계">
      <div className="flowStageCopy">
        <span className="flowStageEyebrow">상담원 업무 흐름</span>
        <strong>{current === 'upload' ? '통화 후 자료를 정리합니다.' : '통화 중 바로 기록합니다.'}</strong>
        <p>
          {current === 'upload'
            ? '녹취·이미지·문서를 추가하고 저장하면, 오른쪽 2단계에서 바로 변호사 검토로 전달할 수 있어요.'
            : '통화를 시작하고 메모를 남기면, 상담이 끝난 뒤 다음 단계(자료 올리기)로 이어집니다.'}
        </p>
      </div>
      <div className="flowStageSteps">
        {stages.map((stage, index) => {
          const Icon = stage.icon;
          const active = current === stage.key;
          const canNavigate = !active && Boolean(onNavigate);
          return (
            <article
              className={active ? 'flowStageStep active' : canNavigate ? 'flowStageStep linkable' : 'flowStageStep'}
              key={stage.key}
              {...(canNavigate ? {
                role: 'button',
                tabIndex: 0,
                onClick: onNavigate,
                onKeyDown: (event) => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); onNavigate(); } },
              } : {})}
            >
              <span className="flowStageIndex">{index + 1}</span>
              <div className="flowStageText">
                <strong><Icon size={15} strokeWidth={2.2} /> {stage.title}</strong>
                <small>{stage.detail}</small>
              </div>
              {active ? <em className="flowStageHereBadge">현재 화면</em> : null}
              {canNavigate ? <ChevronRight className="flowStageGo" size={16} strokeWidth={2.4} aria-hidden="true" /> : null}
            </article>
          );
        })}
      </div>
    </section>
  );
}

// 상담 검토 요청에 이미 담긴 법률구조 대상 정보(사람이 읽는 라벨)를, 이 화면의 select가 쓰는
// key 값으로 되돌립니다. 기존 상담을 골랐을 때 폼을 그 상담의 현재 값으로 채우는 데 씁니다.
function resolveLegalAidTypeKey(applicantTypeLabel) {
  const matched = legalAidApplicantTypes.find((item) => item.label === applicantTypeLabel);
  return matched ? matched.key : 'none';
}

function buildEligibilityDraftFromCase(selectedCase) {
  const check = selectedCase?.eligibilityCheck;
  return {
    legalAidType: check ? resolveLegalAidTypeKey(check.applicantType) : 'none',
    eligibilityEvidenceSubmitted: Boolean(check?.evidenceSubmitted),
  };
}

// 통화 전에 자료부터 올려두는 드문 경우를 위한 자동 제목입니다. 상담자 이름·제목은
// 실시간 상담 화면에서 통화 중에 채우므로 여기서는 입력받지 않습니다. (코치 피드백)
function buildAutoUploadTitle() {
  const now = new Date();
  const label = `${String(now.getMonth() + 1).padStart(2, '0')}/${String(now.getDate()).padStart(2, '0')} ${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}`;
  return `상담 자료 올리기 (${label} 등록)`;
}

// 업로드 자료 종류(녹취록/신분증/증빙자료)는 드롭존 옆 select로 고르고, 실제 파일 받기는
// 드롭존 하나로 통일합니다. 버튼 세 개를 늘어놓던 이전 방식보다 화면이 훨씬 단순해집니다.
const uploadCategoryOptions = ['녹취록', '신분증', '증빙자료'];

// 자료 유형별로 받을 파일 종류를 제한합니다.
//
// 유형은 뒤 단계에서 파일을 어떻게 처리할지를 정합니다 — 녹취록은 STT로 텍스트를 뽑고,
// 신분증·증빙자료는 OCR/문서 추출로 갑니다. 녹취록 자리에 사진이 들어가면 STT가 처리할 수
// 없는 파일을 붙들게 되고, 상담원은 분석 결과에 녹취 내용이 왜 없는지 한참 뒤에야 알게 됩니다.
// 고르는 순간 막아서 그런 상황 자체를 없앱니다.
const uploadCategoryAccept = {
  '녹취록': '.mp3,.wav,.m4a',
  '신분증': '.jpg,.jpeg,.png',
  '증빙자료': '.pdf,.hwp,.hwpx,.doc,.docx,.txt',
};

function fileMatchesCategory(file, category) {
  const allowed = uploadCategoryAccept[category];
  if (!allowed) return true;
  const dot = file.name.lastIndexOf('.');
  const ext = dot === -1 ? '' : file.name.slice(dot).toLowerCase();
  return allowed.split(',').includes(ext);
}

function FileDropzone({ category, onCategoryChange, onAddFiles }) {
  const [isDragOver, setIsDragOver] = useState(false);
  const [fileError, setFileError] = useState('');
  const inputId = React.useId();
  const showToast = useToast();
  const handleFiles = (fileList) => {
    if (!fileList || !fileList.length) return;
    // accept 속성은 파일 선택창만 걸러줍니다. 드래그앤드롭으로 들어온 파일은 그대로 통과하므로
    // 여기서 한 번 더 확인합니다.
    const files = Array.from(fileList);
    const accepted = files.filter((file) => fileMatchesCategory(file, category));
    const rejected = files.filter((file) => !fileMatchesCategory(file, category));
    if (rejected.length) {
      showToast(
        `${category}에는 ${uploadCategoryAccept[category]} 파일만 올릴 수 있습니다 (제외: ${rejected.map((file) => file.name).join(', ')})`,
        'warn',
      );
      setFileError(`${category}에는 허용된 파일 형식만 추가할 수 있습니다.`);
    }
    if (accepted.length) onAddFiles(category, accepted);
  };
  return (
    <div
      className={isDragOver ? 'fileDropzone dragOver' : 'fileDropzone'}
      onDragOver={(event) => { event.preventDefault(); setIsDragOver(true); }}
      onDragLeave={() => setIsDragOver(false)}
      onDrop={(event) => {
        event.preventDefault();
        setIsDragOver(false);
        handleFiles(event.dataTransfer.files);
      }}
      >
      <div className="fileDropzoneCopy">
        <strong>자료 유형을 선택한 뒤 파일을 추가하세요.</strong>
      </div>
      <div className="fileDropzoneControls">
        <div className="fileDropzoneStep">
          <div className="fileCategoryChoices" role="group" aria-label="자료 유형 선택">
            {uploadCategoryOptions.map((option) => (
              <button
                className={category === option ? 'active' : ''}
                type="button"
                key={option}
                aria-pressed={category === option}
                onClick={() => { onCategoryChange(option); setFileError(''); }}
              >
                {option}
              </button>
            ))}
          </div>
        </div>
        <div className="fileDropzoneStep fileDropzonePickStep">
          <label className="fileBtn" htmlFor={inputId}>
            파일 선택
            <input
              id={inputId}
              type="file"
              multiple
              accept={uploadCategoryAccept[category] || ''}
              onChange={(event) => {
                handleFiles(event.target.files);
                event.target.value = '';
              }}
            />
          </label>
        </div>
      </div>
      {fileError ? <p className="fileDropzoneError" role="alert">{fileError}</p> : null}
    </div>
  );
}

// 법률구조 대상 확인 + 파일 업로드는 '새 상담 만들기'와 '기존 상담에 자료 추가' 두 경로에서
// 완전히 같은 모양으로 쓰이므로, 한 군데(SRP)에 모아 두 곳에서 재사용합니다.
function EligibilityAndFilesSection({ legalAidType, eligibilityEvidenceSubmitted, onChangeLegalAidType, onChangeEvidenceSubmitted, files, onAddFiles, onRemoveFile }) {
  const [dropzoneCategory, setDropzoneCategory] = useState(uploadCategoryOptions[2]);
  const selectedApplicantType = legalAidApplicantTypes.find((item) => item.key === legalAidType) || legalAidApplicantTypes[0];
  const isLegalAidApplicant = legalAidType !== 'none';
  const eligibilityBadgeText = getEligibilityBadgeText(isLegalAidApplicant, eligibilityEvidenceSubmitted);
  const eligibilityHelperText = getEligibilityHelperText(isLegalAidApplicant, eligibilityEvidenceSubmitted);
  return (
    <>
      <section className="eligibilityPanel">
        <div className="eligibilityHeader">
          <div>
            <h3><ShieldCheck size={16} strokeWidth={2.2} className="sectionIcon" aria-hidden="true" /> 무료 법률구조 대상 확인</h3>
            <p>대상 유형과 증빙자료 제출 여부</p>
          </div>
          <span className={`statusChip ${isLegalAidApplicant ? (eligibilityEvidenceSubmitted ? 'tone-success' : 'tone-warn') : 'tone-muted'}`}>
            {isLegalAidApplicant ? (eligibilityEvidenceSubmitted ? <CheckCircle2 size={13} strokeWidth={2.4} aria-hidden="true" /> : <XCircle size={13} strokeWidth={2.4} aria-hidden="true" />) : null}
            {eligibilityBadgeText}
          </span>
        </div>
        <div className="formGrid">
          <label className="field">
            <span>대상자 유형</span>
            <ChoicePicker
              options={legalAidApplicantTypes.map((item) => ({ value: item.key, label: item.label, description: item.evidence }))}
              value={legalAidType}
              onChange={onChangeLegalAidType}
              placeholder="대상자 유형 선택"
            />
          </label>
          <div className="evidenceBox">
            <span>필요 증빙서류</span>
            <strong>{selectedApplicantType.evidence}</strong>
            {isLegalAidApplicant ? (
              <label className="evidenceCheck">
                <input
                  className="evidenceCheckInput"
                  type="checkbox"
                  checked={eligibilityEvidenceSubmitted}
                  onChange={(event) => onChangeEvidenceSubmitted(event.target.checked)}
                />
                증빙서류 제출 확인
                <em className={eligibilityEvidenceSubmitted ? 'evidenceStatus submitted' : 'evidenceStatus missing'}>
                  {eligibilityEvidenceSubmitted ? '제출 확인' : '미제출'}
                </em>
              </label>
            ) : null}
          </div>
        </div>
        <p className={isLegalAidApplicant && !eligibilityEvidenceSubmitted ? 'eligibilityWarning' : 'helperText'}>
          {eligibilityHelperText}
        </p>
      </section>
      <div className="workflowColumns uploadFileWorkspace">
        <div className="uploadDropzoneColumn">
          <h3><UploadCloud size={16} strokeWidth={2.2} className="sectionIcon" aria-hidden="true" /> 상담 자료 추가</h3>
          <p className="helperText">녹취 · 이미지 · 문서를 함께 분석합니다. 저장하면 업로드됩니다.</p>
          <FileDropzone category={dropzoneCategory} onCategoryChange={setDropzoneCategory} onAddFiles={onAddFiles} />
        </div>
        <div className="uploadListColumn">
          <h3><Paperclip size={16} strokeWidth={2.2} className="sectionIcon" aria-hidden="true" /> 업로드 목록</h3>
          <div className="scrollBox">
            {files.length ? files.map((file, index) => (
              <button type="button" className="uploadItem" key={file.id || file.fileKey || `${file.name}-${index}`} onClick={() => onRemoveFile(index)}>
                {/* 서버에 이미 저장된 첨부는 core-api가 파일 크기를 내려주지 않아 file.size가 없습니다.
                    0KB로 표시하면 빈 파일처럼 보이므로, 크기를 알 때만 괄호를 붙입니다. */}
                <span className="uploadItemName" title={file.name}><FileText size={13} strokeWidth={2.2} aria-hidden="true" /> [{file.category}] {file.name}{file.size ? ` (${Math.ceil(file.size / 1024)}KB)` : ''}</span>
                <span className={`uploadItemStatus statusChip ${uploadStatusTone(file.status)}`}>{file.status || '대기'}</span>
                <span className="uploadItemRemove"><Trash2 size={12} strokeWidth={2.4} aria-hidden="true" /> 삭제</span>
              </button>
            )) : <p>아직 추가한 파일이 없습니다.</p>}
          </div>
        </div>
      </div>
    </>
  );
}

// 코치 피드백: 상담자 이름·상담 제목 입력은 없애고, 상담을 '선택'해서 통화가 끝난 뒤
// 후처리로 자료를 올려 변호사가 검토하도록 재구성합니다. 아직 상담이 하나도 없을 때만
// (드문 경우) 최소 정보로 새 상담을 만드는 경로를 남겨둡니다.
function UploadWorkbench({ consultations = [], onCreateConsultation, onUpdateConsultation, onGoToRealtimeAnalysis }) {
  const showToast = useToast();
  const confirm = useConfirm();
  const hasExistingCase = consultations.length > 0;
  const [creatingNew, setCreatingNew] = useState(!hasExistingCase);
  const [selectedId, setSelectedId] = useState(hasExistingCase ? consultations[0].id : null);
  const selectedCase = !creatingNew ? consultations.find((item) => String(item.id) === String(selectedId)) : null;
  const canUploadAfterAnalysis = Boolean(selectedCase?.analysis || selectedCase?.analysisSaved || selectedCase?.analysisStatus === 'COMPLETED');
  const [message, setMessage] = useState('');

  const emptyNewForm = { category: caseCategories[0].key, type: caseCategories[0].subTypes[0], memo: '', legalAidType: 'none', eligibilityEvidenceSubmitted: false };
  const savedDraft = readStorage(storageKeys.uploadDraft, null);
  const [newForm, setNewForm] = useState(savedDraft?.form || emptyNewForm);
  const [newFiles, setNewFiles] = useState(savedDraft?.files || []);
  const newActiveCategory = caseCategories.find((category) => category.key === newForm.category) || caseCategories[0];

  // 기존 상담을 고르면 그 상담에 이미 저장된 법률구조 대상 정보·첨부자료를 바로 이어서 편집합니다.
  const [existingFiles, setExistingFiles] = useState(selectedCase?.attachments || []);
  const [existingEligibility, setExistingEligibility] = useState(() => buildEligibilityDraftFromCase(selectedCase));
  useEffect(() => {
    if (creatingNew) return;
    setExistingFiles(selectedCase?.attachments || []);
    setExistingEligibility(buildEligibilityDraftFromCase(selectedCase));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedId, creatingNew]);

  // 파일을 고르면 일단 목록에만 추가합니다(즉시 S3 업로드 X). 실제 S3 업로드는 사용자가
  // "임시저장" 또는 "상담 만들고 자료 저장"/"자료 저장" 버튼을 눌렀을 때 uploadPendingFiles가
  // 한 번에 수행합니다. → 파일만 골라보고 저장 없이 화면을 벗어나면 애초에 업로드 자체가
  // 일어나지 않아, 버려지는 파일이 S3 버킷에 쌓이지 않습니다.
  const addFilesTo = (setFilesState, label, selectedFiles) => {
    const staged = Array.from(selectedFiles).map((file) => createAttachmentMetadata(file, label));
    if (!staged.length) return;
    setFilesState((items) => [...items, ...staged]);
    setMessage(`${label} ${staged.length}개 추가 · 저장 시 업로드됩니다`);
  };
  // "삭제"는 그 파일이 실제로 어디까지 저장돼 있는지에 따라 다르게 처리합니다.
  //  - DB(Attachment)에 이미 등록됨(attachmentId 있음) → 백엔드가 DB row + S3 오브젝트를 함께 지웁니다.
  //  - 아직 등록 전이지만 S3에는 이미 올라가 있음(fileKey만 있음 — 예: "새 상담 만들기"에서 상담을
  //    만들기 전에 지우는 경우) → 등록되지 않은 S3 오브젝트 전용 삭제 경로로 지웁니다.
  //  - 둘 다 없으면(로컬에서 방금 고르기만 함) 지울 서버 실체가 없으므로 목록에서만 뺍니다.
  // 실패하면 목록에서 빼지 않습니다 — "지웠는데 서버·S3엔 그대로 남아있는" 불일치를 막기 위함입니다.
  // draftKey를 주면(=아직 상담이 없는 새 상담 만들기 초안) 로컬스토리지 draft도 같이 갱신해서,
  // "임시저장"을 다시 누르지 않아도 지운 파일이 새로고침 후 되살아나지 않게 합니다.
  const removeFileAt = async (setFilesState, files, index, coreId, draftKey) => {
    const target = files[index];
    if (!target) return undefined;
    try {
      if (target.attachmentId && coreId) {
        await deleteCoreAttachment(coreId, target.attachmentId);
      } else if (target.fileKey) {
        await deleteUnregisteredCoreAttachment(target.fileKey);
      }
    } catch (error) {
      showToast(`삭제 실패: ${friendlyErrorMessage(error, '잠시 후 다시 시도해 주세요.')}`, 'warn');
      return undefined;
    }
    const nextFiles = files.filter((_, itemIndex) => itemIndex !== index);
    setFilesState(nextFiles);
    if (draftKey) {
      const savedDraft = readStorage(draftKey, null);
      if (savedDraft) writeStorage(draftKey, { ...savedDraft, files: nextFiles });
    }
    return nextFiles;
  };

  // 업로드는 됐지만(fileKey 있음) 아직 이 상담의 DB에 등록되지 않은 파일(attachmentId 없음)을
  // 등록합니다. coreId가 없으면(=아직 core-api에 없는 상담, 예: 새 상담 만들기 흐름) 등록할 곳이
  // 없어 건너뜁니다 — 그 흐름은 상담 생성 자체가 attachments를 함께 등록하므로 이 호출이 필요 없습니다.
  const registerNewAttachments = async (files, coreId) => {
    if (!coreId) return files;
    const unregistered = files.filter((item) => item.fileKey && !item.attachmentId);
    if (!unregistered.length) return files;
    let result = files;
    for (const item of unregistered) {
      try {
        const saved = await registerCoreAttachment(coreId, item);
        result = result.map((file) => file.id === item.id ? { ...file, attachmentId: saved.id, status: '서버 저장' } : file);
      } catch (error) {
        showToast(`${item.name} 등록 실패: ${friendlyErrorMessage(error, '잠시 후 다시 시도해 주세요.')}`, 'warn');
      }
    }
    return result;
  };

  // 저장 동작(임시저장·자료 저장)에서 호출해, 그때까지 S3에 올라가지 않은 파일(fileKey 없음 —
  // 신규 선택분뿐 아니라 이전 시도에서 실패했거나 백엔드 미지원으로 로컬 보관 중이던 파일도 포함)을
  // 한 번에 업로드합니다. 최신 상태가 반영된 파일 목록을 돌려주므로 호출부는 이 값을 그대로
  // draft 저장/첨부 payload 생성에 씁니다.
  const uploadPendingFiles = async (files, setFilesState) => {
    const pending = files.filter((item) => item.file && !item.fileKey);
    if (!pending.length) return files;
    const pendingIds = new Set(pending.map((item) => item.id));
    setFilesState((items) => items.map((item) => pendingIds.has(item.id) ? { ...item, status: '업로드 중' } : item));
    setMessage(`파일 ${pending.length}개 업로드 중…`);

    let result = files;
    let fellBackToLocal = false;
    let failedCount = 0;
    let sttFailedCount = 0;
    for (const meta of pending) {
      let sttResult = null;
      const isAudio = /\.(mp3|wav|m4a|webm)$/i.test(meta.name || '') || /audio\//i.test(meta.mimeType || '');
      if (isAudio) {
        try {
          setMessage(`${meta.name} 음성을 텍스트로 변환 중…`);
          sttResult = await transcribeAudio(meta.file);
        } catch (error) {
          sttFailedCount += 1;
          showToast(`${meta.name} 음성 텍스트 변환 실패: ${friendlyErrorMessage(error, '잠시 후 다시 시도해 주세요.')}`, 'warn');
        }
      }
      try {
        const { fileKey, fileUrl } = await uploadFileToS3(meta.file, meta.category);
        result = result.map((item) => item.id === meta.id ? {
          ...item,
          fileKey,
          uploadedUrl: fileUrl,
          ...(sttResult ? {
            extractedText: sttResult.originalText,
            sttOriginalText: sttResult.originalText,
            sttMaskedText: sttResult.anonymizedText,
            sttAnonymizationMap: sttResult.anonymizationMap,
          } : {}),
          status: sttResult ? '업로드·텍스트 변환 완료' : '업로드 완료',
        } : item);
      } catch (error) {
        if (error instanceof S3UploadUnavailableError) {
          fellBackToLocal = true;
          result = result.map((item) => item.id === meta.id ? { ...item, status: '로컬 보관 (업로드 대기)' } : item);
        } else {
          failedCount += 1;
          result = result.map((item) => item.id === meta.id ? { ...item, status: '업로드 실패' } : item);
          showToast(`${meta.name} 업로드 실패: ${friendlyErrorMessage(error, '잠시 후 다시 시도해 주세요.')}`, 'warn');
        }
      }
      setFilesState(result);
    }
    setMessage(fellBackToLocal
      ? `파일 업로드 완료. 일부는 업로드 대기${sttFailedCount ? ` · STT ${sttFailedCount}건 실패` : ''}` //업로드 대기=로컬 임시 보관
      : failedCount
        ? `파일 업로드 완료. ${failedCount}건 실패${sttFailedCount ? ` · STT ${sttFailedCount}건 실패` : ''}`
        : `파일 업로드 완료${sttFailedCount ? ` · STT ${sttFailedCount}건 실패` : ''}.`);
    return result;
  };

  const saveDraft = async () => {
    const uploadedFiles = await uploadPendingFiles(newFiles, setNewFiles);
    writeStorage(storageKeys.uploadDraft, { form: newForm, files: uploadedFiles, savedAt: new Date().toISOString() });
    setMessage('임시저장 완료');
  };
  // "비우기"도 "삭제"와 같은 이유로 정리가 필요합니다 — 임시저장 단계에서 이미 S3에 올라간 파일
  // (fileKey는 있지만 아직 어떤 상담에도 등록되지 않아 attachmentId가 없는 파일)을 먼저 지우지 않으면,
  // 로컬 목록·draft만 비워질 뿐 S3에는 그 파일이 그대로 남습니다.
  const clearDraft = async () => {
    const orphaned = newFiles.filter((item) => item.fileKey && !item.attachmentId);
    let failedCount = 0;
    for (const item of orphaned) {
      try {
        await deleteUnregisteredCoreAttachment(item.fileKey);
      } catch {
        failedCount += 1;
      }
    }
    writeStorage(storageKeys.uploadDraft, null);
    setNewForm(emptyNewForm);
    setNewFiles([]);
    if (failedCount) {
      showToast(`S3에 남은 파일 ${failedCount}건을 정리하지 못했습니다.`, 'warn');
      setMessage(`임시저장 비움 · S3 파일 ${failedCount}건 정리 실패`);
    } else {
      setMessage('임시저장 비움');
    }
  };

  const buildAttachmentPayload = (files) => files.map(({ attachmentId, category, name, size, mimeType, storageBucket, fileKey, uploadedUrl, extractedText, sttOriginalText, sttMaskedText, sttAnonymizationMap }) => (
    { attachmentId, category, name, size, mimeType, storageBucket, fileKey, uploadedUrl, extractedText, sttOriginalText, sttMaskedText, sttAnonymizationMap }
  ));
  const buildEligibilityPayload = ({ legalAidType, eligibilityEvidenceSubmitted }) => {
    const selectedApplicantType = legalAidApplicantTypes.find((item) => item.key === legalAidType) || legalAidApplicantTypes[0];
    const isLegalAidApplicant = legalAidType !== 'none';
    return {
      applicantType: selectedApplicantType.label,
      requiredEvidence: selectedApplicantType.evidence,
      isTargetCandidate: isLegalAidApplicant,
      evidenceSubmitted: isLegalAidApplicant ? eligibilityEvidenceSubmitted : false,
    };
  };

  const submitNewCase = async () => {
    const accepted = await confirm({
      title: '자료를 저장할 상담을 만들까요?',
      message: '최소 정보로 상담을 만듭니다.\n이름·제목은 실시간 상담에서 채워주세요.',
      confirmLabel: '만들기',
      cancelLabel: '다시 확인',
      tone: 'info',
    });
    if (!accepted) return;
    const uploadedFiles = await uploadPendingFiles(newFiles, setNewFiles);
    const result = await onCreateConsultation({
      name: '',
      title: buildAutoUploadTitle(),
      category: newForm.category,
      type: newForm.type,
      memo: newForm.memo,
      status: '진행 중',
      eligibilityCheck: buildEligibilityPayload(newForm),
      attachments: buildAttachmentPayload(uploadedFiles),
    }, { skipNavigation: true });
    if (result?.id == null) {
      showToast('상담을 만들지 못했습니다. 다시 시도해주세요.', 'warn');
      return;
    }
    writeStorage(storageKeys.uploadDraft, null);
    setNewForm(emptyNewForm);
    setNewFiles([]);
    setMessage('');
    setCreatingNew(false);
    setSelectedId(result.id);
    showToast(result?.message || '자료 저장 완료 · 실시간 상담에서 이어서 진행', result?.coreSynced === false ? 'warn' : 'success');
  };

  const submitExistingCase = async () => {
    if (!selectedCase) return;
    if (!canUploadAfterAnalysis) {
      setMessage('실시간 상담을 끝내고 분석을 완료한 상담만 자료를 올릴 수 있습니다.');
      return;
    }
    const accepted = await confirm({
      title: '자료를 저장할까요?',
      message: `${selectedCase.caseNo} 「${selectedCase.title}」\n첨부자료와 구조대상 확인 내용을 저장합니다.`,
      confirmLabel: '저장',
      cancelLabel: '다시 확인',
      tone: 'info',
    });
    if (!accepted) return;
    const uploadedFiles = await uploadPendingFiles(existingFiles, setExistingFiles);
    // S3까지는 올라갔어도 아직 이 상담의 Attachment DB row가 없는 파일(방금 새로 고른 파일)을
    // 여기서 등록합니다 — 이걸 하지 않으면 화면에는 보이지만 DB에는 없는 파일이 생깁니다.
    const registeredFiles = await registerNewAttachments(uploadedFiles, selectedCase.coreId);
    setExistingFiles(registeredFiles);
    onUpdateConsultation(selectedCase.id, {
      eligibilityCheck: buildEligibilityPayload(existingEligibility),
      attachments: buildAttachmentPayload(registeredFiles),
    });
    setMessage('');
    showToast('자료 저장 완료 · 검토 요청 시 함께 전달', 'success');
  };

  return (
    <main className="workspacePage">
      <div className="workflowIntro uploadWorkflowIntro">
        <h1><FileText size={22} strokeWidth={2.2} className="workflowIntroIcon" aria-hidden="true" /> 상담 자료 올리기</h1>
        <p>상담을 선택하고 자료를 추가한 뒤 변호사 검토로 전달하세요.</p>
      </div>
      <section className="workflowPanel uploadPanel">
        <CounselorFlowStage current="upload" onNavigate={onGoToRealtimeAnalysis ? () => onGoToRealtimeAnalysis() : undefined} />
        <section className="uploadWorkCard" aria-label="상담 자료 올리기 작업 영역">
        {hasExistingCase ? (
          <div className="seg uploadModeSwitch" role="tablist" aria-label="자료 업로드 방식">
            <button type="button" role="tab" aria-selected={!creatingNew} className={!creatingNew ? 'active' : ''} onClick={() => { setCreatingNew(false); setMessage(''); }}>
              기존 상담에 자료 추가
            </button>
            <button type="button" role="tab" aria-selected={creatingNew} className={creatingNew ? 'active' : ''} onClick={() => { setCreatingNew(true); setMessage(''); }}>
              새 상담 만들기
            </button>
          </div>
        ) : null}
        {!creatingNew && hasExistingCase ? (
          <label className="field uploadCaseSelector">
            <span><span className="fieldLabelWithIcon"><FolderOpen size={14} strokeWidth={2.4} aria-hidden="true" /> 상담 선택</span></span>
            <CasePicker consultations={consultations} value={selectedId} onChange={(id) => { setSelectedId(id); setMessage(''); }} />
          </label>
        ) : null}

        {creatingNew ? (
          <>
            <div className="newUploadGuide">
              <strong><Info size={14} strokeWidth={2.4} aria-hidden="true" /> 통화 전 자료를 먼저 등록합니다.</strong>
              <span>(이름과 제목은 실시간 상담에서 입력합니다.)</span>
            </div>
            <div className="formGrid">
              <label className="field">
                <span>사건 대분류</span>
                <ChoicePicker
                  value={newForm.category}
                  options={caseCategories.map((category) => ({ value: category.key, label: category.key }))}
                  onChange={(nextValue) => {
                    const nextCategory = caseCategories.find((category) => category.key === nextValue) || caseCategories[0];
                    setNewForm({ ...newForm, category: nextCategory.key, type: nextCategory.subTypes[0] });
                  }}
                  placeholder="사건 대분류 선택"
                />
              </label>
              <label className="field">
                <span>사건 소분류</span>
                <ChoicePicker
                  value={newForm.type}
                  options={newActiveCategory.subTypes.map((type) => ({ value: type, label: type }))}
                  onChange={(nextValue) => setNewForm({ ...newForm, type: nextValue })}
                  placeholder="사건 소분류 선택"
                />
              </label>
            </div>
            <label className="field">
              <span>상담 내용 입력 <em className="charCount">{newForm.memo.length}자</em></span>
              <textarea
                className="tallTextarea"
                value={newForm.memo}
                onChange={(e) => setNewForm({ ...newForm, memo: e.target.value })}
                placeholder="상담 내용을 입력하세요."
              />
            </label>
            <EligibilityAndFilesSection
              legalAidType={newForm.legalAidType}
              eligibilityEvidenceSubmitted={newForm.eligibilityEvidenceSubmitted}
              onChangeLegalAidType={(value) => setNewForm({ ...newForm, legalAidType: value, eligibilityEvidenceSubmitted: false })}
              onChangeEvidenceSubmitted={(checked) => setNewForm({ ...newForm, eligibilityEvidenceSubmitted: checked })}
              files={newFiles}
              onAddFiles={(label, files) => addFilesTo(setNewFiles, label, files)}
              onRemoveFile={(index) => removeFileAt(setNewFiles, newFiles, index, null, storageKeys.uploadDraft)}
            />
            <div className="uploadActionRow">
              <div className="uploadSecondaryActions">
                <button type="button" onClick={saveDraft}>임시저장</button>
                <button type="button" onClick={clearDraft}>임시저장 비우기</button>
              </div>
              <button className="primaryButton uploadSubmitButton" type="button" onClick={submitNewCase}>상담 만들고 자료 저장</button>
            </div>
          </>
        ) : selectedCase ? (
          <>
            <div className="uploadCaseSummary">
              <div className="uploadCaseSummaryInfo">
                <span><FolderOpen size={14} strokeWidth={2.4} aria-hidden="true" /> 선택한 상담</span>
                <strong>{selectedCase.caseNo}</strong>
              </div>
              <div className={`uploadCaseSummaryStatus ${canUploadAfterAnalysis ? 'is-ready' : 'is-waiting'}`}>
                {canUploadAfterAnalysis ? <CheckCircle2 size={16} strokeWidth={2.4} aria-hidden="true" /> : <XCircle size={16} strokeWidth={2.4} aria-hidden="true" />}
                <span>
                  <strong>{canUploadAfterAnalysis ? '자료를 추가할 수 있어요' : '분석을 먼저 완료해주세요'}</strong>
                  <small>{canUploadAfterAnalysis ? '필요한 녹취·이미지·문서를 등록하세요.' : '실시간 상담에서 분석을 완료하면 자료를 저장할 수 있어요.'}</small>
                </span>
              </div>
            </div>
            <EligibilityAndFilesSection
              legalAidType={existingEligibility.legalAidType}
              eligibilityEvidenceSubmitted={existingEligibility.eligibilityEvidenceSubmitted}
              onChangeLegalAidType={(value) => setExistingEligibility({ legalAidType: value, eligibilityEvidenceSubmitted: false })}
              onChangeEvidenceSubmitted={(checked) => setExistingEligibility((current) => ({ ...current, eligibilityEvidenceSubmitted: checked }))}
              files={existingFiles}
              onAddFiles={(label, files) => addFilesTo(setExistingFiles, label, files)}
              onRemoveFile={async (index) => {
                const nextFiles = await removeFileAt(setExistingFiles, existingFiles, index, selectedCase?.coreId, null);
                if (nextFiles) onUpdateConsultation(selectedCase.id, { attachments: buildAttachmentPayload(nextFiles) });
              }}
            />
            <div className="uploadActionRow">
              <span className="uploadSaveHint">{canUploadAfterAnalysis ? '파일을 추가한 뒤 저장하면 변호사 검토에 함께 전달됩니다.' : '분석 완료 전에는 자료를 저장할 수 없습니다.'}</span>
              <button className="primaryButton uploadSubmitButton" type="button" onClick={submitExistingCase} disabled={!canUploadAfterAnalysis}>자료 저장</button>
            </div>
          </>
        ) : (
          <InlineEmptyNotice>등록된 상담이 없습니다. 새 상담을 만들어 주세요.</InlineEmptyNotice>
        )}
        {message ? <p className="helperText">{message}</p> : null}
        </section>
      </section>
    </main>
  );
}

// 멀티모달 분석: 면담 텍스트뿐 아니라 녹취(mp3 등)·이미지·문서 첨부자료까지 함께 고려해서
// 사건 유형/긴급도 후보를 산출한다는 것을 화면에서 확인할 수 있도록 구성했습니다.
function summarizeAttachmentModalities(attachments = []) {
  const audio = attachments.filter((item) => /mp3|wav|m4a/i.test(item.mimeType || item.name || ''));
  const image = attachments.filter((item) => /png|jpe?g/i.test(item.mimeType || item.name || ''));
  const document = attachments.filter((item) => /pdf|hwpx|doc/i.test(item.mimeType || item.name || ''));
  return [
    { key: '녹취(mp3 등)', count: audio.length },
    { key: '이미지(png/jpg)', count: image.length },
    { key: '문서(pdf/hwpx 등)', count: document.length },
  ];
}

// AI 백본(ai-api) case_analysis 출력의 extracted_content_detail을 화면에 그대로 보여주기 위한 mock 생성기입니다.
// 노트북 기준 파일별 상태: success(추출 성공) / empty(내용없음) / unsupported(레거시 hwp 등 변환 필요) / failed(다운로드·추출 실패)
function buildExtractionDetail(attachments = []) {
  return attachments.map((item) => {
    const name = item.name || '';
    const isHwpx = /\.hwpx$/i.test(name) || /hwpx/i.test(item.mimeType || '');
    const isLegacyHwp = /\.hwp$/i.test(name) || /hwp/i.test(item.mimeType || '') && !isHwpx;
    const isAudio = /mp3|wav|m4a/i.test(item.mimeType || name);
    const status = isLegacyHwp ? 'unsupported' : 'success';
    const fileType = isAudio ? 'audio_video' : isLegacyHwp ? 'legacy_hwp_convert_required' : isHwpx ? 'hwpx_document' : /png|jpe?g/i.test(name) ? 'image' : 'document';
    return {
      fileLink: item.fileKey || item.uploadedUrl || name,
      fileName: name,
      fileType,
      status,
      // 서식 자동 채움은 표/셀 XML 접근이 가능한 hwpx를 기준으로 처리합니다. 이 note는 화면에
      // 그대로 노출되는 문구라(코치 피드백: 개발자 용어를 유저 친화적으로), 내부 기술 이름
      // (Whisper·XML·레거시)은 빼고 상담원이 바로 이해할 수 있는 말로 풀어 씁니다.
      note: isLegacyHwp ? '예전 형식(.hwp) 파일이에요. 최신 형식(.hwpx)으로 바꾸면 자동 채움에 쓸 수 있어요.' : isHwpx ? '문서의 표·항목에서 자동으로 값을 채울 수 있어요.' : isAudio ? '통화 음성을 텍스트로 변환해 분석했습니다.' : '문서 텍스트 추출',
    };
  });
}

function buildAttachmentLinkMetadata(attachments = []) {
  return attachments.map((item) => ({
    category: item.category || '',
    fileName: item.name || item.fileName || '',
    fileType: item.mimeType || item.fileType || '',
    storageBucket: item.storageBucket || '',
    fileKey: item.fileKey || '',
    fileUrl: item.uploadedUrl || item.fileUrl || '',
    status: item.status || '',
  })).filter((item) => item.fileName || item.fileKey || item.fileUrl);
}

function attachmentLinkValues(attachments = []) {
  return buildAttachmentLinkMetadata(attachments)
    .map((item) => item.fileKey || item.fileUrl || item.fileName)
    .filter(Boolean);
}

// STT 개인정보 마스킹(한현우 STT Privacy Filter 파트) 미리보기용 mock 마스커.
// 실제 마스킹은 ai-api STT 단계에서 수행되며, 프론트는 원문/마스킹본 토글로 검토자에게 보여줍니다.
//
// TODO(규제): 아직 어느 단계에서도 실제 마스킹이 일어나지 않습니다.
//   ai-api 쪽에 마스킹 코드가 없고(app 전체 검색 0건), 아래 sttPreview는 고정 예시 문장이라
//   어느 상담을 열어도 같은 문장이 나옵니다. 실제 녹취록은 이 화면을 지나지 않습니다.
//   보호조치 기준 제10조(개인정보 표시 제한) 항목이며, 담당 파트가 붙기 전까지는
//   화면의 해당 카드에 "예시"임을 표시해 실제 동작으로 오해되지 않게 하는 편이 안전합니다.
//   가이드 30쪽: 상담원 화면과 변호사 화면이 서로 다른 방식으로 가리면 두 화면을 조합해
//   원본을 복원할 수 있으므로, 실제 적용 시 두 화면의 마스킹 방식을 통일해야 합니다.
function maskSensitiveText(text = '') {
  return text
    .replace(/\d{6}\s*-\s*\d{7}/g, '[RRN]') // 주민등록번호
    .replace(/01[016789]\s*-?\s*\d{3,4}\s*-?\s*\d{4}/g, '[PHONE]') // 휴대전화
    .replace(/\d{2,4}\s*-\s*\d{3,4}\s*-\s*\d{4}/g, '[PHONE]'); // 유선전화
}

// 분석 결과에서 '상담을 받으러 온 사람'의 이름을 고릅니다.
//
// extracted_json.당사자는 [{역할, 이름}] 목록이고 상대방·피상속인까지 함께 들어 있어서,
// 아무거나 집으면 상대방 이름이 상담자 자리에 들어갑니다. 역할을 보고 골라야 합니다.
// '미상'처럼 확인 못 했다는 표시는 이름이 아니므로 거릅니다 — 그걸 채우면 화면에
// "상담받은 사람: 미상"이 뜨고, 서식에도 그대로 실려 나갑니다.
const CLIENT_ROLE_ORDER = ['청구인', '신청인', '내담자', '원고', '상속인'];
const UNKNOWN_NAME_MARKS = ['미상', '불명', '확인불가', '확인 불가', '알 수 없음', '없음'];

export function pickClientName(analysis) {
  const parties = analysis?.extractedJson?.당사자;
  if (!Array.isArray(parties) || !parties.length) return '';

  const usable = parties.filter((party) => {
    const name = (party?.이름 || '').trim();
    if (!name) return false;
    return !UNKNOWN_NAME_MARKS.some((mark) => name.includes(mark));
  });
  if (!usable.length) return '';

  for (const role of CLIENT_ROLE_ORDER) {
    const matched = usable.find((party) => (party?.역할 || '').includes(role));
    if (matched) return matched.이름.trim();
  }
  // 역할명이 예상 밖이면(예: '신고인') 첫 당사자를 씁니다. 상담자가 먼저 언급되는 게 보통입니다.
  return usable[0].이름.trim();
}

function buildAnalysisResult(selectedCase) {
  const text = selectedCase?.memo || selectedCase?.title || '';
  const attachments = selectedCase?.attachments || [];
  const attachmentLinks = buildAttachmentLinkMetadata(attachments);
  const submittedFileLinks = attachmentLinkValues(attachments);
  const modalities = summarizeAttachmentModalities(attachments);
  const hasMultimodalEvidence = modalities.some((item) => item.count > 0);
  const audioAttachments = attachments.filter((item) => /mp3|wav|m4a|webm/i.test(item.mimeType || item.name || ''));
  const sttOriginal = audioAttachments.map((item) => item.sttOriginalText || item.extractedText).filter(Boolean).join('\n\n');
  const sttMasked = audioAttachments.map((item) => item.sttMaskedText || item.extractedText).filter(Boolean).join('\n\n');
  // 긴급도 등급/점수/근거와 구조대상 판정은 '구조대상 판정' 버튼과 같은 규칙(공용 함수)으로 산출합니다.
  const emergency = computeCaseEmergency(selectedCase);
  const { eligibilityCheck, isTargetCandidate, evidenceSubmitted, eligibility } = resolveEligibilityFromCase(selectedCase);
  const missingInfo = [
    ...(!attachments.length ? ['증빙자료'] : []),
    ...(isTargetCandidate && !evidenceSubmitted ? [`${eligibilityCheck?.requiredEvidence || '대상자 증빙서류'}`] : []),
    '상대방 인적사항',
    '계약/거래 일자',
  ];
  return {
    summary: text
      ? `${selectedCase.title} 상담 내용${hasMultimodalEvidence ? '과 첨부자료(녹취/이미지/문서)' : ''}을 기준으로 사건 유형, 필요자료, 구조검토 항목을 정리했습니다.`
      : '상담 내용 부족 · 요약 불가',
    caseType: selectedCase?.type || '미분류',
    // 백본 CaseTypeResult.reason (분류 근거, 참고용 표현)
    caseTypeReason: text ? `상담 요약과 첨부자료 내용을 종합할 때 '${selectedCase?.type || '해당 유형'}'으로 보임 (참고용 분류).` : '분류 근거를 산출할 상담 내용이 부족합니다.',
    urgency: emergency.level,
    // 백본 EmergencyResult (case_emergency_level / case_emergency_ratio / reason)
    emergency,
    eligibility,
    eligibilityCheck,
    missingInfo,
    // 누락 자료 각 항목의 제출 상태. 기본은 '미제출'이고, 상담원이 받으면 '제출'로 바꿉니다.
    evidenceStatus: Object.fromEntries(missingInfo.map((item) => [item, 'missing'])),
    checklist: [
      { label: '법률구조 대상 여부 확인', checked: Boolean(eligibilityCheck) },
      { label: '법률구조 대상자 증빙서류 제출 여부 확인', checked: !isTargetCandidate || evidenceSubmitted },
      { label: '승소 가능성 기초자료 확인', checked: false },
      { label: '추가자료 요청 필요 여부 확인', checked: false },
    ],
    timeline: [
      { date: today, text: '상담 접수 및 인공지능 분석 후보 생성' },
    ],
    modalities,
    sourceAttachments: attachmentLinks,
    extractedJson: {
      attachment_links: attachmentLinks,
      submitted_file_link: submittedFileLinks,
    },
    // 파일별 STT/문서추출 처리 상태 (노트북에서 UI 연동 권장한 extracted_content_detail)
    extractionDetail: buildExtractionDetail(attachments),
    // STT 개인정보 마스킹 미리보기 (원문 → 마스킹본)
    sttPreview: {
      original: sttOriginal || '녹취 파일의 STT 결과가 아직 없습니다.',
      masked: sttMasked || '녹취 파일의 개인정보 가림 결과가 아직 없습니다.',
    },
    verification: {
      // AI 응답 검증(형식/근거/환각 탐지, 요구사항 AI-07 시리즈)을 화면에서 확인할 수 있도록 만든 mock 검증 결과입니다.
      format: true,
      grounded: attachments.length > 0,
      hallucinationRisk: !text,
    },
  };
}

// 변호사 검토 결과 배너의 좌측 색 바를 결정 종류에 맞게 고릅니다(승인=그린/반려=레드/그 외=옐로).
function reviewActionTone(status) {
  if (status === '승인') return 'success';
  if (status === '반려') return 'danger';
  return 'warn';
}

// 통화 시간을 "3:07"처럼 분:초로 보여줍니다. 실제 통화(텔레포니) 연동 전까지는 이 타이머가
// 상담원에게 "지금 통화가 진행 중이다"를 보여주는 유일한 신호라 정확히 맞춰둡니다.
function formatCallDuration(totalSeconds) {
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${minutes}:${String(seconds).padStart(2, '0')}`;
}

// 코치 피드백: "실시간 통화 버튼 누르면 시작되고, 종료 버튼 누르면 끝난 다음, 분석 시작을 누르면
// 바로 분석을 시작하는 방식". 실제 전화 연동(WebRTC 등)은 백엔드 작업이 필요해 아직 없지만,
// 상담원이 겪는 절차 자체(시작 → 통화 중 메모 → 종료 → 분석 시작)는 지금 화면에서 실제로 동작합니다.
// 통화 중 경과 시간을 보여주는 라이브 인디케이터. 버튼 라벨에 시간을 붙이면 버튼이 매초
// 넓이가 바뀌어 깜빡여 보이므로, 버튼과 분리해 깜빡이는 점 + 고정폭 숫자로만 보여줍니다.
function CallLiveIndicator({ seconds }) {
  return (
    <span className="callLiveIndicator" role="status">
      <span className="callLiveDot" aria-hidden="true" />
      <span className="callLiveTime">{formatCallDuration(seconds)}</span>
    </span>
  );
}

function RealtimeCallControl({
  hasCase,
  callStatus,
  callSeconds,
  audioStatus,
  availableAudioCalls,
  selectedAudioCallId,
  isLoadingAudioCalls,
  onSelectAudioCall,
  onRefreshAudioCalls,
  onStartCall,
  onEndCall,
}) {
  const sttChip = callStatus === 'ongoing'
    ? audioStatus === 'streaming'
      ? { tone: 'tone-success', label: '통화 오디오 전송 중 · 메모로 기록' }
      : audioStatus === 'error'
        ? { tone: 'tone-warn', label: '오디오 연결 실패 · 메모로 기록' }
        // 연결할 통화를 고르지 않고 시작한 경우(화면 확인용 등)는 오디오 연결 자체를
        // 시도하지 않으므로, "연결 중"이 아니라 지금 상태를 있는 그대로 알려줍니다.
        : audioStatus === 'idle'
          ? { tone: 'tone-muted', label: '오디오 연결 없이 진행 중 · 메모로 기록' }
          : { tone: 'tone-info', label: '통화 오디오 연결 중 · 메모로 기록' }
    : audioStatus === 'error'
      ? { tone: 'tone-warn', label: '통화 연결 실패 · 목록을 새로고침해주세요' }
      : isLoadingAudioCalls
        ? { tone: 'tone-info', label: '진행 중인 통화 확인 중' }
        : availableAudioCalls.length
          ? { tone: 'tone-info', label: '연결할 통화를 선택해주세요' }
          : { tone: 'tone-muted', label: '연결 가능한 통화를 기다리는 중' };
  return (
    <div className="realtimeStatusChips">
      {callStatus === 'idle' ? (
          <>
            <div className="audioCallPicker">
              <label htmlFor="audio-call-picker">연결할 통화</label>
              <div className="audioCallPickerControls">
                <select
                  id="audio-call-picker"
                  value={selectedAudioCallId}
                  onChange={(event) => onSelectAudioCall(event.target.value)}
                  disabled={!hasCase || isLoadingAudioCalls}
                >
                  <option value="">{isLoadingAudioCalls ? '통화 목록을 불러오는 중...' : '대기 중인 통화 선택'}</option>
                  {availableAudioCalls.map((call) => (
                    <option key={call.callId} value={call.callId}>통화 ID · {call.callId}</option>
                  ))}
                </select>
                <button type="button" className="audioCallRefreshButton" onClick={() => onRefreshAudioCalls()} disabled={isLoadingAudioCalls}>
                  새로고침
                </button>
              </div>
            </div>
          <button type="button" className="callControlButton start" onClick={onStartCall} disabled={!hasCase || isLoadingAudioCalls}>
            <PhoneCall size={14} strokeWidth={2.4} /> 통화 시작
          </button>
          </>
        ) : callStatus === 'ongoing' ? (
          <>
            <button type="button" className="callControlButton end" onClick={onEndCall}>
              <PhoneCall size={14} strokeWidth={2.4} /> 통화 종료
            </button>
            <CallLiveIndicator seconds={callSeconds} />
          </>
        ) : (
          <span className="statusChip tone-success"><Check size={13} strokeWidth={2.4} /> 통화 종료됨 · {formatCallDuration(callSeconds)}</span>
        )}
      <span className={`statusChip ${sttChip.tone}`}><Mic size={13} strokeWidth={2.4} /> {sttChip.label}</span>
      <span className={`statusChip ${hasCase ? 'tone-info' : 'tone-muted'}`}><Check size={13} strokeWidth={2.4} /> 메모 · {hasCase ? '입력 가능' : '사건 선택 필요'}</span>
    </div>
  );
}

// 통화 중 곧바로 타이핑할 수 있는 실제 입력창입니다. 여기 적은 내용이 selectedCase.memo로 저장되고,
// 아래 'AI 분석 결과'가 그대로 이 텍스트를 분석 대상으로 씁니다 — 즉 이 칸을 채우는 것이
// 실시간 분석을 정확하게 만드는 가장 중요한 행동입니다.
function RealtimeMemoCard({ selectedCase, onUpdateConsultation }) {
  const hasCase = Boolean(selectedCase);
  const memo = selectedCase?.memo || '';
  const charCount = memo.trim().length;
  const [pendingMemo, setPendingMemo] = useState('');
  const addMemo = () => {
    const nextLine = pendingMemo.trim();
    if (!hasCase || !nextLine) return;
    onUpdateConsultation(selectedCase.id, { memo: memo ? `${memo}\n${nextLine}` : nextLine });
    setPendingMemo('');
  };
  return (
    <article className="realtimeTranscriptCard">
      <div className="realtimeTranscriptHead">
        <h3><MessageSquareText size={16} strokeWidth={2.2} className="sectionIcon" aria-hidden="true" /> 실시간 상담 메모</h3>
        <span className={`statusChip ${charCount ? 'tone-info' : 'tone-muted'}`}>
          {charCount ? <Check size={12} strokeWidth={2.4} aria-hidden="true" /> : <Clock size={12} strokeWidth={2.4} aria-hidden="true" />}
          {charCount ? `${charCount}자 기록됨` : '작성 전'}
        </span>
      </div>
      {/* 이 칸은 실제로는 읽기 전용 기록 로그입니다(입력은 아래 작은 입력창으로). 그런데
          placeholder가 "여기 바로 적어주세요"라고 말해, 정작 이 칸을 눌러 타이핑을 시도했다가
          아무 반응이 없는 사람이 있었습니다(코치 피드백). 안내 문구를 실제 동작에 맞춥니다. */}
      <textarea
        className="realtimeMemoTextarea"
        value={memo}
        disabled={!hasCase}
        readOnly
        placeholder={hasCase
          ? '아래 입력창에 적으면 여기에 기록됩니다.'
          : '사건 선택 또는 새 상담 시작'}
      />
      <div className="realtimeMemoComposer">
        <input
          value={pendingMemo}
          disabled={!hasCase}
          onChange={(event) => setPendingMemo(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === 'Enter') {
              event.preventDefault();
              addMemo();
            }
          }}
          placeholder="통화 내용을 바로 적어주세요."
        />
        <button type="button" className="callAnalyzeButton" onClick={addMemo} disabled={!hasCase || !pendingMemo.trim()}>메모 추가</button>
      </div>
      <p className="helperText">AI 분석 기준 메모</p>
    </article>
  );
}

// 상담원이 통화 중 무엇을 더 물어볼지 놓치지 않도록, 지금까지 적은 메모에서 키워드를 찾아
// 물어보면 좋을 질문을 제안합니다. 클릭해서 '질문함'으로 표시하는 것 외에는 아무 것도 자동으로 하지 않고,
// 실제로 무엇을 물을지는 상담원이 판단합니다(참고용 제안일 뿐, 자동화된 응답이 아닙니다).
const FOLLOWUP_QUESTION_RULES = [
  { keyword: '계약', question: '계약서를 직접 갖고 계신가요? 계약 체결일과 조건을 확인해 주시겠어요?' },
  { keyword: '연락', question: '상대방과 마지막으로 연락한 날짜와 방법을 알려주시겠어요?' },
  { keyword: '금액', question: '정확한 금액과 지급 기한을 확인해 주시겠어요?' },
  { keyword: '폭행', question: '진단서나 상해를 확인할 수 있는 자료가 있으신가요?' },
  { keyword: '이혼', question: '혼인 신고일과 별거를 시작한 시점을 알려주시겠어요?' },
  { keyword: '체불', question: '근로계약서와 임금 명세서를 갖고 계신가요?' },
];

const DEFAULT_FOLLOWUP_QUESTIONS = [
  '사건이 발생한 정확한 날짜를 알려주시겠어요?',
  '상대방의 연락처나 주소를 알고 계신가요?',
  '관련된 증빙 자료(계약서, 문자, 녹취 등)를 갖고 계신가요?',
];

function buildSuggestedQuestions(memoText) {
  const matched = FOLLOWUP_QUESTION_RULES.filter((rule) => memoText.includes(rule.keyword)).map((rule) => rule.question);
  const suggestions = matched.length ? matched : DEFAULT_FOLLOWUP_QUESTIONS;
  return Array.from(new Set(suggestions)).slice(0, 4);
}

function RealtimeSuggestedQuestions({ memoText }) {
  const [askedQuestions, setAskedQuestions] = useState([]);
  const suggestions = buildSuggestedQuestions(memoText);

  const toggleAsked = (question) => {
    setAskedQuestions((current) => current.includes(question) ? current.filter((item) => item !== question) : [...current, question]);
  };

  return (
    <article className="realtimeQuestionsCard">
      <div className="realtimeTranscriptHead">
        <h3><Sparkles size={16} strokeWidth={2.2} className="sectionIcon" aria-hidden="true" /> AI 추천 추가 질문</h3>
        <span className="statusChip tone-info"><Info size={12} strokeWidth={2.4} aria-hidden="true" />통화 중 참고용</span>
      </div>
      <p className="helperText">메모 기반 질문 후보 · 상담원이 선택</p>
      <div className="realtimeQuestionList">
        {suggestions.map((question) => {
          const asked = askedQuestions.includes(question);
          return (
            <button
              type="button"
              key={question}
              className={asked ? 'realtimeQuestionItem asked' : 'realtimeQuestionItem'}
              onClick={() => toggleAsked(question)}
              aria-pressed={asked}
            >
              <span>{question}</span>
              <em>{asked ? <><Check size={12} strokeWidth={2.6} aria-hidden="true" />질문함</> : '질문하기'}</em>
            </button>
          );
        })}
      </div>
    </article>
  );
}

// 통화 중 실시간 자막이 뜰 자리입니다. 백엔드 STT 연동 전까지는 항상 빈 배열이라 안내
// 문구만 보이지만, RealtimeAudioStream.onTranscript가 채워주는 값을 그대로 받는 구조라
// 백엔드가 자막 프레임을 보내기 시작하면 코드 변경 없이 바로 통화 내용이 흘러갑니다.
function LiveCaptionCard({ callStatus, audioStatus, captions }) {
  if (callStatus !== 'ongoing') return null;
  const isStreaming = audioStatus === 'streaming';
  return (
    <article className="realtimeCaptionCard">
      <div className="realtimeTranscriptHead">
        <h3><Mic size={16} strokeWidth={2.2} className="sectionIcon" aria-hidden="true" /> 실시간 자막</h3>
        <span className={`statusChip ${isStreaming ? 'tone-info' : 'tone-muted'}`}>
          {isStreaming ? <Mic size={12} strokeWidth={2.4} aria-hidden="true" /> : <Clock size={12} strokeWidth={2.4} aria-hidden="true" />}
          {isStreaming ? '연동 준비 중' : '오디오 연결 대기'}
        </span>
      </div>
      {captions.length ? (
        <div className="realtimeCaptionList" role="log" aria-live="polite">
          {captions.map((caption, index) => (
            <p key={index} className={caption.isFinal ? 'realtimeCaptionLine' : 'realtimeCaptionLine pending'}>{caption.text}</p>
          ))}
        </div>
      ) : (
        <p className="helperText">
          통화 음성을 실시간 글자로 바꿔 보여줄 자리입니다. 지금은 연동 전이라 비어 있고, 통화 내용은 왼쪽 메모에 직접 적어 주세요.
        </p>
      )}
    </article>
  );
}

function RealtimeAnalysisPanel({ selectedCase, onUpdateConsultation, callStatus, callSeconds, audioStatus, liveCaptions, availableAudioCalls, selectedAudioCallId, isLoadingAudioCalls, onSelectAudioCall, onRefreshAudioCalls, onStartCall, onEndCall, caseMeta }) {
  const hasCase = Boolean(selectedCase);
  const headline = callStatus === 'ongoing'
    ? '통화 중입니다. 들은 내용을 바로 적으면서 진행하세요.'
    : callStatus === 'ended'
      ? '통화를 마쳤습니다. 메모를 다듬은 뒤 분석을 시작하세요.'
      : '전화를 받으면 위 ‘통화 시작’을 눌러 진행하세요.';
  return (
    <section className="realtimeWorkbenchPanel roleAccent-counselor" aria-label="실시간 상담 메모">
      <div className="realtimeWorkbenchHeader">
        <div>
          <span className="roleIdentityBadge roleIdentityBadge-counselor"><Headphones size={12} strokeWidth={2.4} aria-hidden="true" /> 상담원 업무</span>
          <span className="flowStageEyebrow"><Radio size={13} strokeWidth={2.4} aria-hidden="true" /> 실시간 상담</span>
          <strong>{headline}</strong>
          <p>통화 내용 자동 받아쓰기를 준비 중입니다. 현재는 메모를 기준으로 분석합니다.</p>
        </div>
        <RealtimeCallControl
          hasCase={hasCase}
          callStatus={callStatus}
          callSeconds={callSeconds}
          audioStatus={audioStatus}
          availableAudioCalls={availableAudioCalls}
          selectedAudioCallId={selectedAudioCallId}
          isLoadingAudioCalls={isLoadingAudioCalls}
          onSelectAudioCall={onSelectAudioCall}
          onRefreshAudioCalls={onRefreshAudioCalls}
          onStartCall={onStartCall}
          onEndCall={onEndCall}
        />
      </div>
      <div className="realtimeConsultationLayout">
        <div className="realtimeConsultationMain">
          <LiveCaptionCard callStatus={callStatus} audioStatus={audioStatus} captions={liveCaptions} />
          <RealtimeMemoCard selectedCase={selectedCase} onUpdateConsultation={onUpdateConsultation} />
          {hasCase ? <RealtimeSuggestedQuestions memoText={selectedCase?.memo || ''} /> : null}
        </div>
        <aside className="realtimeConsultationSide">
          {caseMeta}
        </aside>
      </div>
    </section>
  );
}

// 코치 피드백: "실시간 상담 때 서식을 추천 및 초안 작성을 해주고". 분석이 끝나면 곧바로
// 이 화면 안에서 추천 서식을 보여주고, 한 번의 클릭으로 사건이 선택된 채 서식 생성 화면으로
// 넘어가게 합니다(예전엔 메뉴를 옮겨 사건을 다시 골라야 했습니다).
// coreId·분석id가 있으면 실제 ai-api 추천(recommendCoreForms)을, 없으면 로컬 휴리스틱
// (recommendTemplates, DraftWorkbench와 같은 함수)을 그대로 재사용합니다.
// 서식 추천을 가져옵니다. 실시간 상담 분석 화면과 서식 생성 화면이 같이 씁니다.
//
// 예전엔 두 화면이 각자 recommendCoreForms를 불러서, 분석 화면에서 추천을 본 뒤
// 초안 만들기로 넘어가면 같은 상담·같은 분석인데도 처음부터 다시 돌렸습니다
// (ai-api 임베딩 검색 + GPT 재랭킹이라 몇 초 걸립니다).
//
// 순서대로 찾습니다.
//   1) 저장된 분석의 recommendation_json — 새로고침해도 남아 있는 유일한 자리
//   2) 이번 세션 메모리 캐시 — 아직 저장 전이라도 화면 사이를 오갈 때 재사용
//   3) 없으면 API 호출 후 두 곳에 모두 남김
function useFormRecommendations(selectedCase) {
  const coreId = selectedCase?.coreId;
  const analysisId = selectedCase?.coreAnalysisId;
  const canUseCoreApi = Boolean(coreId && analysisId);
  // 저장된 분석에 이미 추천이 들어 있으면 그걸 그대로 씁니다.
  const savedRecommendations = selectedCase?.analysis?.recommendation?.recommendations;

  const initial = (Array.isArray(savedRecommendations) && savedRecommendations.length)
    ? savedRecommendations
    : (readCachedFormRecommendations(coreId, analysisId) || []);

  const [aiRecommendations, setAiRecommendations] = useState(initial);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!canUseCoreApi) { setAiRecommendations([]); return undefined; }

    if (Array.isArray(savedRecommendations) && savedRecommendations.length) {
      cacheFormRecommendations(coreId, analysisId, savedRecommendations);
      setAiRecommendations(savedRecommendations);
      return undefined;
    }
    const cached = readCachedFormRecommendations(coreId, analysisId);
    if (cached) { setAiRecommendations(cached); return undefined; }

    let cancelled = false;
    setAiRecommendations([]);
    setLoading(true);
    recommendCoreForms(coreId, analysisId)
      .then((response) => {
        const list = response?.recommendations || [];
        cacheFormRecommendations(coreId, analysisId, list);
        if (!cancelled) setAiRecommendations(list);
      })
      .catch(() => { if (!cancelled) setAiRecommendations([]); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [canUseCoreApi, coreId, analysisId, savedRecommendations]);

  return { aiRecommendations, loading };
}

function RecommendedFormsPanel({ selectedCase, onSaveBeforeOpen, saving }) {
  const draftCaseType = resolveConfirmedCaseType(selectedCase);
  const { aiRecommendations, loading } = useFormRecommendations(selectedCase);

  // 실제 ai-api 추천이 있으면 'AI 추천' 배지를, 없어 로컬 휴리스틱으로 대체한 경우는
  // '추천' 배지로 구분해 어떤 근거로 골랐는지 헷갈리지 않게 합니다.
  const usingAiRecommendations = Boolean(aiRecommendations.length);
  const localTemplateNames = draftCaseType ? recommendTemplates(draftCaseType).map((item) => item.templateName) : [];
  const templateNames = (usingAiRecommendations
    ? aiRecommendations.map((item) => item.form_name).filter(Boolean)
    : localTemplateNames
  ).slice(0, 3);

  return (
    <section className="recommendedFormsPanel">
      <div className="recommendedFormsHeader">
        <div>
          <h3><Sparkles size={16} strokeWidth={2.2} className="sectionIcon" aria-hidden="true" /> 추천 서식</h3>
          <p>{draftCaseType ? `${draftCaseType} 기준 추천` : '사건 유형 확정 후 추천'}</p>
        </div>
      </div>
      {loading ? <p className="helperText">추천 서식을 불러오는 중…</p> : null}
      {templateNames.length ? (
        <div className="recommendedFormsList">
          {templateNames.map((name) => (
            <div className="tmplRow" key={name}>
              <span className="tmplRowName">
                <FileText size={14} strokeWidth={2.2} aria-hidden="true" /> {name}
                <em className={`tmplRowBadge statusChip ${usingAiRecommendations ? 'tone-info' : 'tone-muted'}`}>
                  {usingAiRecommendations ? <Star size={11} strokeWidth={2.4} aria-hidden="true" /> : null} {usingAiRecommendations ? 'AI 추천' : '추천'}
                </em>
              </span>
              {/* 넘어가기 전에 저장까지 합니다. 예전엔 저장을 따로 눌러야 했고, 안 누르고
                  넘어가면 서식 화면에서 분석 결과 없이 시작해 추천이 로컬 휴리스틱으로
                  떨어졌습니다. 저장 버튼과 같은 함수(performSaveAnalysis)를 부르므로
                  저장 경로가 둘로 갈리지 않습니다. */}
              {/* 예전엔 추천 서식 3개 중 무엇을 눌러도 항상 caseId만 넘겨서, 서식 생성
                  화면은 어느 걸 눌렀는지 모르고 매번 같은(초기) 서식으로 열렸습니다
                  (코치 피드백). 어떤 서식을 눌렀는지도 함께 넘깁니다. */}
              <button
                type="button"
                className="secondaryActionButton compactAction"
                onClick={() => onSaveBeforeOpen?.(selectedCase.id, name)}
                disabled={!onSaveBeforeOpen || saving}
              >
                {saving ? '저장하는 중...' : '저장하고 초안 만들기'}
              </button>
            </div>
          ))}
        </div>
      ) : <p className="helperText">분석 저장 후 추천 가능</p>}
    </section>
  );
}

function AnalysisWorkbench({ consultations, onCreateConsultation, onUpdateConsultation, onRequestLegalReview, onAnalysisSaved, currentUser, onGoToDashboard, onOpenDraft, focusedConsultationId, analysisRuns = {}, onStartAnalysis }) {
  const [selectedId, setSelectedId] = useState(focusedConsultationId || caseOptions(consultations)[0].id);
  const [analyzed, setAnalyzed] = useState(false);
  const selectedCase = consultations.find((item) => String(item.id) === String(selectedId));
  // 이 상담의 분석이 App에서 돌고 있는지. 화면을 떠났다 돌아와도 App이 계속 들고 있으므로
  // 여기서는 그 값을 읽기만 하면 됩니다("분석 중... 1:53" 표시가 그대로 이어집니다).
  const activeRun = analysisRuns[selectedCase?.id];
  // selectedId가 가리키는 사건이 consultations 목록에 없으면(예: focusedConsultationId로 들어왔다가
  // 그 사건이 삭제됐거나, 최초 마운트 시점의 목록과 지금 목록이 달라진 경우) selectedCase가
  // 계속 undefined로 남아 통화 시작·메모 입력이 영구히 비활성화됩니다. CasePicker는 그래도 첫
  // 사건 정보를 보여줄 수 있어(placeholder가 아니라) 사용자는 사건이 선택된 것처럼 보이는데
  // 실제로는 아무것도 못 하는 상태가 됩니다. 유효한 사건이 있다면 자동으로 첫 사건으로 되돌립니다.
  useEffect(() => {
    if (focusedConsultationId) return;
    if (!consultations.length) return;
    const stillExists = consultations.some((item) => String(item.id) === String(selectedId));
    if (!stillExists) setSelectedId(consultations[0].id);
  }, [consultations, selectedId, focusedConsultationId]);
  // 통화 시작/종료 상태입니다. 실제 전화 연동 전까지는 상담원이 직접 누르는 버튼으로 관리하고,
  // 사건을 바꾸면(다른 상담을 고르면) 이전 통화 상태가 남아있지 않도록 초기화합니다.
  const [callStatus, setCallStatus] = useState('idle');
  const [callSeconds, setCallSeconds] = useState(0);
  const [audioStatus, setAudioStatus] = useState('idle');
  const [availableAudioCalls, setAvailableAudioCalls] = useState([]);
  const [selectedAudioCallId, setSelectedAudioCallId] = useState('');
  const [isLoadingAudioCalls, setIsLoadingAudioCalls] = useState(false);
  // 실시간 자막(통화 중 STT) 자리입니다. 백엔드가 아직 자막 프레임을 보내지 않아 항상 빈
  // 배열로 남지만(코치 피드백: 실시간 통화 기술 중 프론트가 먼저 준비해둘 수 있는 부분),
  // RealtimeAudioStream의 onTranscript가 연결돼 있어 백엔드가 붙으면 바로 채워집니다.
  const [liveCaptions, setLiveCaptions] = useState([]);
  const audioStreamRef = useRef(null);
  useEffect(() => {
    audioStreamRef.current?.stop();
    audioStreamRef.current = null;
    setCallStatus('idle');
    setCallSeconds(0);
    setAudioStatus('idle');
    setSelectedAudioCallId('');
    setLiveCaptions([]);
  }, [selectedId]);
  useEffect(() => {
    if (callStatus !== 'ongoing') return undefined;
    const timer = setInterval(() => setCallSeconds((seconds) => seconds + 1), 1000);
    return () => clearInterval(timer);
  }, [callStatus]);
  const startCall = async () => {
    if (!selectedCase) return;
    setCallStatus('ongoing');
    setCallSeconds(0);
    setLiveCaptions([]);
    // 연결할 통화를 아직 고르지 않았어도(대기 중인 통화가 없거나, 화면만 확인하려는 경우)
    // 통화 중 화면 자체는 볼 수 있어야 합니다. 이때는 실제 오디오 스트림 연결 없이
    // 메모 중심으로만 진행하고, 나중에 통화를 고르면 '통화 시작'을 다시 눌러 오디오까지 붙일 수 있습니다.
    if (!selectedAudioCallId) {
      setAudioStatus('idle');
      return;
    }
    try {
      const stream = createRealtimeAudioStream({
        onStatus: (status) => {
          setAudioStatus(status);
          if (status === 'ended') setCallStatus('ended');
        },
        onError: () => setAudioStatus('error'),
        // 자막 프레임이 오면 이어붙이고, 아직 확정되지 않은(isFinal:false) 마지막 줄은
        // 다음 프레임이 올 때 갱신해 덮어씁니다(흔한 스트리밍 STT 관례: 중간 결과는 계속
        // 바뀌다가 isFinal:true로 확정됩니다).
        onTranscript: ({ text, isFinal }) => {
          setLiveCaptions((current) => {
            const last = current[current.length - 1];
            if (last && !last.isFinal) return [...current.slice(0, -1), { text, isFinal }];
            return [...current, { text, isFinal }];
          });
        },
      });
      audioStreamRef.current = stream;
      await stream.start({ callId: selectedAudioCallId });
    } catch (error) {
      setCallStatus('idle');
      setAudioStatus('error');
      showToast(friendlyErrorMessage(error, '오디오 연결에 실패했습니다. 메모로 계속 진행할 수 있습니다.'), 'warn');
    }
  };
  // 통화 종료 버튼을 누르면 곧바로 '분석 시작'을 누를 수 있는 상태가 됩니다(통화 중에는 분석을
  // 막아 상담원이 먼저 통화를 마치도록 유도합니다).
  const endCall = () => {
    audioStreamRef.current?.stop();
    audioStreamRef.current = null;
    setAudioStatus('idle');
    setCallStatus('ended');
  };
  useEffect(() => () => audioStreamRef.current?.stop(), []);
  const [chosen, setChosen] = useState([]);
  const [analysis, setAnalysis] = useState(null);
  const [timelineText, setTimelineText] = useState('');
  const [savedMessage, setSavedMessage] = useState('');
  const [reviewMessage, setReviewMessage] = useState('');
  const [aiTaskMessage, setAiTaskMessage] = useState('');
  const [aiResultSummary, setAiResultSummary] = useState(null);
  const [analysisSaved, setAnalysisSaved] = useState(false);
  // 구조대상·누락자료 버튼처럼 이 화면 안에서 끝나는 짧은 작업의 진행 상태입니다.
  // 사건 분석 자체는 App이 돌리므로(analysisRuns) 여기서 관리하지 않습니다.
  const [isLocalTaskRunning, setIsLocalTaskRunning] = useState(false);
  // 분석 버튼을 잠글지 판단하는 값 — App에서 도는 사건 분석과 이 화면의 짧은 작업 둘 다 포함.
  const isAnalyzing = Boolean(activeRun) || isLocalTaskRunning;
  // 구조대상·누락자료 버튼은 보통 분석 시작에서 받아둔 결과를 재사용해 즉시 끝나지만,
  // 분석 전에 이 버튼부터 누르면 실제로 분석이 돌아 몇십 초가 걸립니다. 그때도 멈춘 것처럼
  // 보이지 않도록 경과 시간을 따로 셉니다.
  const [localElapsedSec, setLocalElapsedSec] = useState(0);
  const analysisElapsedSec = activeRun?.elapsedSec ?? localElapsedSec;
  const [isStartingQuickSession, setIsStartingQuickSession] = useState(false);
  // useAsyncAction(전역 로딩 오버레이)은 여기서 더 이상 쓰지 않습니다 — 분석이 몇 분씩 걸려서,
  // 화면 전체를 덮으면 그동안 다른 상담을 볼 수도 접수할 수도 없었습니다(startAnalysis 주석 참고).
  const showToast = useToast();
  const refreshAvailableAudioCalls = async ({ silent = false } = {}) => {
    setIsLoadingAudioCalls(true);
    try {
      const calls = await fetchAvailableAudioCalls();
      setAvailableAudioCalls(calls);
      setSelectedAudioCallId((currentCallId) => (
        calls.some((call) => call.callId === currentCallId)
          ? currentCallId
          : ''
      ));
    } catch (error) {
      setAvailableAudioCalls([]);
      setSelectedAudioCallId('');
      if (!silent) {
        showToast(friendlyErrorMessage(error, '진행 중인 통화 목록을 불러오지 못했습니다.'), 'warn');
      }
    } finally {
      setIsLoadingAudioCalls(false);
    }
  };
  useEffect(() => {
    // 외부 전화 서버가 먼저 통화를 등록하는 구조라, 상담원이 화면을 열어 둔 채로도
    // 새 통화를 확인할 수 있게 대기 상태에서만 목록을 주기적으로 갱신합니다.
    // 초기/자동 갱신 실패는 토스트를 띄우지 않고, 직접 새로고침했을 때만 안내합니다.
    if (callStatus !== 'idle') return undefined;
    refreshAvailableAudioCalls({ silent: true });
    const refreshTimer = window.setInterval(() => {
      refreshAvailableAudioCalls({ silent: true });
    }, 5000);
    return () => window.clearInterval(refreshTimer);
  }, [callStatus]);
  const [showMaskedStt, setShowMaskedStt] = useState(true);
  // 상담원이 각 분석 섹션(AI 분석 요약 등)을 확인했는지 스스로 표시해두는 용도라, 서버에
  // 저장하지 않는 화면 전용 상태입니다. 사건을 바꾸면(selectCase/포커스 진입) 같이 비웁니다.
  const [confirmedSections, setConfirmedSections] = useState({});
  const toggleSectionConfirmed = (key) => setConfirmedSections((current) => ({ ...current, [key]: !current[key] }));
  const [pendingHitlAction, setPendingHitlAction] = useState(null);
  const activeReviewAction = selectedCase?.reviewAction && !selectedCase.reviewAction.resolved ? selectedCase.reviewAction : null;
  // focusedConsultationId(대시보드/알림에서 특정 사건으로 바로 진입)로 들어왔을 때 한 번만
  // selectedId/analysis를 맞춰준다. consultations를 deps에 그대로 두면(사건이 아직 안
  // 실려 있을 때 재시도하려고 필요) startAnalysis()의 onUpdateConsultation(coreAnalysisId
  // 패치)만으로도 consultations 참조가 바뀌어 이 effect가 다시 돌아, 방금 setAnalysis로
  // 반영한 새 분석 결과를 focusedCase.analysis(패치에 없는, 저장 전이라 갱신 안 된 값)로
  // 덮어써버리는 문제가 있었다. appliedFocusIdRef로 같은 focusedConsultationId에 대해서는
  // 한 번만 적용되게 막는다.
  const appliedFocusIdRef = useRef(null);
  useEffect(() => {
    if (!focusedConsultationId) {
      // 포커스가 풀리면(다른 화면으로 이동) 다음에 같은 사건으로 다시 들어와도
      // 새로 동기화되도록 기록을 지운다.
      appliedFocusIdRef.current = null;
      return;
    }
    if (appliedFocusIdRef.current === focusedConsultationId) return;
    const focusedCase = consultations.find((item) => String(item.id) === String(focusedConsultationId));
    if (!focusedCase) return;
    appliedFocusIdRef.current = focusedConsultationId;
    setSelectedId(focusedConsultationId);
    setAnalyzed(Boolean(focusedCase?.analysis));
    setAnalysis(focusedCase?.analysis || null);
    setSavedMessage('');
    setReviewMessage('');
    setAnalysisSaved(Boolean(focusedCase?.analysis));
    setConfirmedSections({});
  }, [focusedConsultationId, consultations]);
  // 이 상담을 진행할 때 도움이 될 후속 작업을 AI가 제안합니다.
  // 각 항목이 '무엇을 하는 것인지' 상담원이 바로 알 수 있도록 설명을 함께 둡니다. (요구사항 AI-04·05 계열)
  const suggestions = [
    { label: '유사 상담 기록 검토', description: '과거 비슷한 사건의 상담 이력을 찾아 참고합니다.' },
    { label: '관련 판례 추천', description: '이 사건 유형에 적용되는 판례를 제안합니다.' },
    { label: '법률 요건 정리', description: '청구가 성립하려면 갖춰야 할 법적 요건을 정리합니다.' },
    { label: '인수인계 요약 생성', description: '다른 담당자가 이어받을 수 있도록 사건 핵심을 요약합니다.' },
    { label: '계약서 등 조사자료 요청', description: '사실관계 확인에 필요한 계약서·증빙 문서를 요청합니다.' },
    { label: '계좌이체내역 확인 요청', description: '금전 거래 정황을 뒷받침할 이체 내역을 확인합니다.' },
    { label: '내용증명 발송 이력 확인', description: '상대방에게 보낸 내용증명이 있는지 확인합니다.' },
  ];
  // 분석 계열 버튼은 전역 로딩 오버레이(runWithLoading)로 감싸지 않습니다.
  //
  // 그 오버레이는 화면 전체를 덮어 클릭을 막는데, 분석은 녹취 길이에 따라 몇 분씩 걸립니다.
  // 그동안 상담원이 다른 상담을 보거나 새 전화를 접수하는 것까지 전부 막힙니다.
  // 대신 아래 progress 콜백으로 경과 시간만 받아 버튼에 표시합니다.
  const trackAnalysisProgress = {
    onProgress: ({ elapsedMs }) => setLocalElapsedSec(Math.floor(elapsedMs / 1000)),
    // 작업 번호를 상담 상태에 남겨 두면 화면을 나갔다 돌아와도 같은 분석 작업을 다시 조회할 수 있습니다.
    onSubmitted: (job) => {
      const jobId = job?.job_id ?? job?.jobId;
      if (jobId != null) onUpdateConsultation(selectedCase.id, { analysisJobId: jobId });
    },
  };

  const applyCompletedAnalysis = (nextAnalysis, { notify = false } = {}) => {
    setAnalysis(nextAnalysis);
    // 통화에서 확인된 상담자 이름을 AI가 채웁니다. 상담원이 직접 입력한 값은 덮어쓰지 않습니다.
    const aiName = pickClientName(nextAnalysis);
    const patch = { analysisJobId: '' };
    if (nextAnalysis.analysisId && nextAnalysis.analysisId !== selectedCase.coreAnalysisId) {
      patch.coreAnalysisId = nextAnalysis.analysisId;
    }
    if (aiName && !selectedCase.name && selectedCase.nameSource !== 'counselor') {
      patch.name = aiName;
      patch.nameSource = 'ai';
    }
    onUpdateConsultation(selectedCase.id, patch);

    setAnalyzed(true);
    setAnalysisSaved(false);
    setSavedMessage('');
    setReviewMessage('');
    setAiTaskMessage('AI 분석 반영 완료');
    setAiResultSummary({
      title: '사건 분석 AI 결과',
      description: '사건 유형 · 긴급도 · 무료 법률구조 대상 검토',
      metrics: [
        { label: '사건 유형', value: nextAnalysis.caseType || '미분류' },
        { label: '긴급도', value: nextAnalysis.urgency || '미확인' },
        { label: '구조대상', value: nextAnalysis.eligibility || '검토 필요' },
      ],
      items: (nextAnalysis.missingInfo || []).slice(0, 4).map((item) => `확인 필요: ${item}`),
    });
    if (notify) showToast('백그라운드 AI 분석이 완료되었습니다.', 'success');
  };

  // 페이지를 이동했다가 돌아온 경우에도, 서버에 남아 있는 분석 작업을 다시 붙잡아 결과를 표시합니다.
  // 완료된 작업은 analysisJobId로 조회하고, 진행 중 작업은 active 엔드포인트로 찾아 이어받습니다.
  useEffect(() => {
    if (!selectedCase?.coreId || selectedCase?.analysis || isAnalyzing) return undefined;
    let cancelled = false;

    const resumeAnalysis = async () => {
      try {
        const knownJob = selectedCase.analysisJobId
          ? await getCoreAnalysisJob(selectedCase.analysisJobId)
          : await findActiveCoreAnalysisJob(selectedCase);
        if (!knownJob || cancelled) return;

        setIsAnalyzing(true);
        setLocalElapsedSec(0);
        setAiTaskMessage('진행 중인 AI 분석 결과를 확인하고 있습니다.');
        const coreResult = await waitForCoreAnalysisJob(knownJob, trackAnalysisProgress);
        if (cancelled) return;
        applyCompletedAnalysis(mergeContractAnalysisResponse(buildAnalysisResult(selectedCase), coreResult), { notify: true });
      } catch (error) {
        if (!cancelled) {
          const message = friendlyErrorMessage(error, '진행 중인 AI 분석 결과를 확인하지 못했습니다.');
          setAiTaskMessage(message);
          showToast(message, 'warn');
        }
      } finally {
        if (!cancelled) setIsAnalyzing(false);
      }
    };

    resumeAnalysis();
    return () => { cancelled = true; };
    // selectedCase가 바뀌었을 때만 기존 작업을 다시 붙잡습니다.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedCase?.id, selectedCase?.coreId, selectedCase?.analysisJobId]);

  // 실행은 App이 맡습니다(startConsultationAnalysis) — 상담원이 분석을 걸어두고 다른 메뉴로
  // 옮겨도 끝까지 진행되고, 끝나면 알림이 뜹니다. 이 화면은 시작만 시키고, 결과는 상담 객체에
  // 실려 돌아오는 것을 아래 effect가 받아 그립니다.
  const startAnalysis = async () => {
    if (!selectedCase || isAnalyzing) return;
    setAiTaskMessage('');
    const result = await onStartAnalysis(selectedCase);
    if (result?.ok || result?.alreadyRunning) return;
    // 분석이 실패하면 화면에 남깁니다. 예전에는 실패도 목업 결과로 덮여 있어서
    // 실패한 사실 자체가 보이지 않았습니다(fetchAnalysisWithFallback 주석 참고).
    const message = result?.error?.message || 'AI 분석에 실패했습니다.';
    setAiTaskMessage(message);
    showToast(message, 'warn');
  };

  // App이 돌린 분석이 끝나면 상담 객체에 결과가 실려 들어옵니다. 화면이 그걸 이어받습니다.
  // 분석 중에 다른 메뉴에 가 있었더라도, 돌아오면 이 effect가 결과를 그려줍니다.
  useEffect(() => {
    const incoming = selectedCase?.analysis;
    if (!incoming || incoming === analysis) return;
    setAnalysis(incoming);
    setAnalyzed(true);
    setAnalysisSaved(false);
    setSavedMessage('');
    setReviewMessage('');
    setAiTaskMessage('AI 분석 반영 완료');
    setAiResultSummary({
      title: '사건 분석 AI 결과',
      description: '사건 유형 · 긴급도 · 무료 법률구조 대상 검토',
      metrics: [
        { label: '사건 유형', value: incoming.caseType || '미분류' },
        { label: '긴급도', value: incoming.urgency || '미확인' },
        { label: '구조대상', value: incoming.eligibility || '검토 필요' },
      ],
      items: (incoming.missingInfo || []).slice(0, 4).map((item) => `확인 필요: ${item}`),
    });
    // analysis를 의존성에 넣으면 사용자가 화면에서 값을 고칠 때마다 이 effect가 다시 돌아
    // 방금 고친 값을 상담에 저장된 것으로 되돌려버립니다. 들어오는 결과만 감시합니다.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedCase?.analysis]);
  const selectCase = (caseId) => {
    const nextCase = consultations.find((item) => String(item.id) === String(caseId));
    setSelectedId(caseId);
    setAnalyzed(Boolean(nextCase?.analysis));
    setAnalysis(nextCase?.analysis || null);
    setChosen([]);
    setTimelineText('');
    setSavedMessage('');
    setReviewMessage('');
    setAiTaskMessage('');
    setAiResultSummary(null);
    setAnalysisSaved(Boolean(nextCase?.analysis));
    setConfirmedSections({});
  };
  // 132콜센터처럼 전화를 받자마자 바로 이야기를 들으며 진행하는 상담은, 상담 문서 업로드 화면에서
  // 이름·제목을 먼저 채우고 오는 절차를 기다릴 수 없습니다. 최소 정보만으로 사건을 즉시 만들고
  // 이 화면(실시간 분석 AI)에 곧장 이어서, 통화 중·통화 후에 사건 정보를 채워 넣을 수 있게 합니다.
  const buildQuickSessionForm = () => {
    const startedAt = new Date();
    const startedLabel = `${String(startedAt.getHours()).padStart(2, '0')}:${String(startedAt.getMinutes()).padStart(2, '0')}`;
    return {
      name: '',
      title: `실시간 상담 (${startedLabel} 접수)`,
      category: caseCategories[0].key,
      type: caseCategories[0].subTypes[0],
      memo: '',
      legalAidType: 'none',
      eligibilityEvidenceSubmitted: false,
      status: '진행 중',
      eligibilityCheck: { applicantType: '해당 없음', requiredEvidence: '대상자 증빙 없음', isTargetCandidate: false, evidenceSubmitted: false },
      attachments: [],
    };
  };
  const startQuickRealtimeSession = async () => {
    if (isStartingQuickSession || !onCreateConsultation) return;
    setIsStartingQuickSession(true);
    try {
      const result = await onCreateConsultation(buildQuickSessionForm(), { skipNavigation: true });
      if (result?.id == null) {
        showToast('실시간 상담을 시작하지 못했습니다. 다시 시도해주세요.', 'warn');
        return;
      }
      selectCase(result.id);
      showToast('실시간 상담 시작 · 통화 중 사건 정보 입력', result.coreSynced === false ? 'warn' : 'success');
    } finally {
      setIsStartingQuickSession(false);
    }
  };
  const updateChecklist = (index) => {
    setAnalysis((current) => ({
      ...current,
      checklist: current.checklist.map((item, itemIndex) => itemIndex === index ? { ...item, checked: !item.checked } : item),
    }));
  };
  // 누락 자료 항목의 제출 상태(미제출 ↔ 제출)를 토글합니다.
  // 상담자에게 자료를 받으면 '제출'로 바꿔, 아직 안 받은 자료가 무엇인지 한눈에 남게 합니다.
  const toggleEvidenceStatus = (item) => {
    setAnalysis((current) => {
      const nextStatus = current.evidenceStatus?.[item] === 'submitted' ? 'missing' : 'submitted';
      return { ...current, evidenceStatus: { ...(current.evidenceStatus || {}), [item]: nextStatus } };
    });
  };
  const caseInfoText = selectedCase ? `${selectedCase.caseNo} · ${selectedCase.name || '상담자 미지정'} · ${selectedCase.title}` : '';
  // 이 둘도 분석 파이프라인을 통째로 다시 돌리므로 startAnalysis와 같은 시간이 걸립니다.
  // 전역 오버레이를 쓰지 않는 이유도 같습니다.
  const runEligibilityCheck = async () => {
    if (!selectedCase || !analysis || isAnalyzing) return;
    setAiTaskMessage('');
    setIsLocalTaskRunning(true);
    setLocalElapsedSec(0);
    try {
      const result = await requestEligibilityCandidate(selectedCase, analysis, trackAnalysisProgress);
      setAnalysis(result);
      // startAnalysis와 같은 이유로 상담에도 반영합니다 — 화면을 벗어났다 와도 남아 있도록.
      onUpdateConsultation(selectedCase.id, { analysis: result });
      setAnalysisSaved(false);
      setAiTaskMessage('구조대상 판정 반영 완료');
      setAiResultSummary(buildAiResultSummary('eligibility', result));
    } catch (error) {
      const message = friendlyErrorMessage(error, '구조대상 확인에 실패했습니다. 잠시 후 다시 시도해 주세요.');
      setAiTaskMessage(message);
      showToast(message, 'warn');
    } finally {
      setIsLocalTaskRunning(false);
    }
  };

  const runMissingDataCheck = async () => {
    if (!selectedCase || !analysis || isAnalyzing) return;
    setAiTaskMessage('');
    setIsLocalTaskRunning(true);
    setLocalElapsedSec(0);
    try {
      const result = await requestMissingDataCandidate(selectedCase, analysis, trackAnalysisProgress);
      setAnalysis(result);
      // startAnalysis와 같은 이유로 상담에도 반영합니다 — 화면을 벗어났다 와도 남아 있도록.
      onUpdateConsultation(selectedCase.id, { analysis: result });
      setAnalysisSaved(false);
      setAiTaskMessage('누락자료 점검 반영 완료');
      setAiResultSummary(buildAiResultSummary('missing', result));
    } catch (error) {
      const message = friendlyErrorMessage(error, '누락자료 점검에 실패했습니다. 잠시 후 다시 시도해 주세요.');
      setAiTaskMessage(message);
      showToast(message, 'warn');
    } finally {
      setIsLocalTaskRunning(false);
    }
  };

  const buildReviewAnalysisPackage = () => {
    const sourceAttachments = analysis?.sourceAttachments?.length
      ? analysis.sourceAttachments
      : buildAttachmentLinkMetadata(selectedCase?.attachments || []);
    const submittedFileLinks = sourceAttachments
      .map((item) => item.fileKey || item.fileUrl || item.fileName)
      .filter(Boolean);

    // 이번에 받아둔 서식 추천도 함께 저장합니다. recommendation_json 컬럼이 계속 비어 있어서,
    // 화면을 옮기거나 새로고침할 때마다 같은 추천을 처음부터 다시 계산하고 있었습니다.
    // 저장해두면 다음에 열 때 바로 뜹니다.
    const cachedRecommendations = readCachedFormRecommendations(
      selectedCase?.coreId, selectedCase?.coreAnalysisId,
    );

    return {
      ...analysis,
      sourceAttachments,
      recommendation: cachedRecommendations?.length
        ? { recommendations: cachedRecommendations }
        : (analysis?.recommendation || {}),
      extractedJson: {
        ...(analysis?.extractedJson || {}),
        attachment_links: sourceAttachments,
        submitted_file_link: submittedFileLinks,
      },
      adoptedItems: chosen,
      counselorReviewNote: [
        `상담원 저장 분석: ${analysis?.summary || '요약 없음'}`,
        `사건유형 ${analysis?.caseType || '미분류'} · 긴급도 ${analysis?.urgency || '미확인'} · 구조대상 ${analysis?.eligibility || '검토 필요'}`,
        chosen.length ? `검토 반영 항목: ${chosen.join(', ')}` : '검토 반영 항목 없음',
      ].join('\n'),
    };
  };

  const performSaveAnalysis = async () => {
    const reviewAnalysis = buildReviewAnalysisPackage();
    onUpdateConsultation(selectedCase.id, {
      analysis: reviewAnalysis,
      workflowStatus: '상담 검토',
      status: '진행 중',
      reviewAction: selectedCase.reviewAction ? { ...selectedCase.reviewAction, resolved: true, resolvedAt: today } : null,
      logs: [...(selectedCase.logs || []), { status: `인공지능 분석 저장: ${reviewAnalysis.eligibility}`, createdAt: today }],
    });
    // 서버 저장 성공 여부를 그대로 문구에 반영합니다. 예전에는 결과와 상관없이 늘
    // "저장 완료"로 시작해서, 서버에 못 갔는데도 저장된 것처럼 읽혔습니다.
    let syncMessage = '';
    let syncFailed = false;
    try {
      const syncResult = await onAnalysisSaved?.(selectedCase, reviewAnalysis);
      syncMessage = syncResult?.message ? ` ${syncResult.message}` : '';
      syncFailed = syncResult ? syncResult.ok === false : false;
    } catch (error) {
      syncMessage = ` ${friendlyErrorMessage(error, '잠시 후 다시 시도해 주세요.')}`;
      syncFailed = true;
    }
    setSavedMessage(syncFailed
      ? `서버 저장 실패:${syncMessage}`
      : `저장 완료: 분석 내용이 저장되고 처리 단계에 반영되었습니다.${syncMessage}`);
    setReviewMessage('');
    setAnalysisSaved(true);
    setAnalysis(reviewAnalysis);
    appendAuditLog({
      actor: currentUser?.email || '상담원',
      action: selectedCase.reviewAction ? '상담 분석 수정 저장' : '상담 분석 저장',
      target: selectedCase.caseNo,
      metadata: {
        title: selectedCase.title,
        caseType: reviewAnalysis.caseType,
        urgency: reviewAnalysis.urgency,
        eligibility: reviewAnalysis.eligibility,
        missingInfo: reviewAnalysis.missingInfo?.join(', ') || '',
        adoptedItems: reviewAnalysis.adoptedItems?.join(', ') || '',
        reviewReason: selectedCase.reviewAction?.reason || '',
      },
    });
  };

  const saveAnalysis = () => {
    setSavedMessage('');
    if (!selectedCase || !analysis) return;
    if (!validateAnalysisResult(analysis)) {
      setSavedMessage('저장 실패: 분석 항목이 모두 채워졌는지 확인해주세요.');
      return;
    }
    setPendingHitlAction({ type: 'save' });
  };

  // 추천 서식에서 '저장하고 초안 만들기'를 눌렀을 때.
  //
  // 저장을 따로 구현하지 않고 저장 버튼과 같은 performSaveAnalysis를 부릅니다. 저장 경로가
  // 둘로 갈리면 한쪽만 고쳐지는 일이 생깁니다(감사 로그, 처리 단계 반영, core-api 동기화가
  // 전부 저 함수 안에 있습니다).
  //
  // 저장을 기다린 뒤에 넘어가야 하는 이유: 서식 화면은 coreAnalysisId로 추천·초안 API를
  // 부르는데, 저장이 끝나기 전에 넘어가면 그 값이 아직 없어 로컬 휴리스틱으로 떨어집니다.
  const [savingBeforeDraft, setSavingBeforeDraft] = useState(false);
  const saveThenOpenDraft = async (caseId, templateName) => {
    if (!selectedCase || !analysis || savingBeforeDraft) return;
    setSavingBeforeDraft(true);
    try {
      if (!analysisSaved) await performSaveAnalysis();
      onOpenDraft?.(caseId, templateName);
    } finally {
      setSavingBeforeDraft(false);
    }
  };

  // 분석 결과가 core-api에 저장돼 있으면(coreId+coreAnalysisId) 실제 검토 상태(AnalysisReviewStatus)도
  // SUBMITTED_FOR_REVIEW로 함께 바꿔둡니다. 아직 core-api에 동기화되지 않은 사건(프로토타입 로컬 진행)에서는
  // 이 호출만 조용히 건너뛰고, 기존 로컬 검토 큐(reviews) 등록은 그대로 진행합니다.
  // 반환값으로 결과를 알립니다. 예전에는 실패해도 console.warn만 찍고 조용히 넘어가서,
  // 변호사 쪽 서버에는 검토 요청이 안 들어갔는데 상담원 화면에는 "등록되었습니다"만 떴습니다.
  // 상담원은 넘긴 줄 알고 손을 떼는데 변호사 목록에는 안 보이는 상태가 됩니다.
  const syncAnalysisReviewToCoreApi = async () => {
    if (!selectedCase.coreId || !selectedCase.coreAnalysisId) {
      return { synced: false, reason: 'not-synced' };
    }
    try {
      await submitCoreAnalysisForReview(selectedCase.coreId, selectedCase.coreAnalysisId);
      return { synced: true };
    } catch (error) {
      console.warn('[분석 검토 요청] core-api 동기화 실패:', error.message);
      return { synced: false, reason: 'error', message: friendlyErrorMessage(error, '서버 연결에 실패했습니다.') };
    }
  };

  const performRequestReview = async () => {
    const sync = await syncAnalysisReviewToCoreApi();
    const result = onRequestLegalReview(selectedCase.id, buildReviewAnalysisPackage());

    if (sync.reason === 'error') {
      // 로컬 큐에는 올라갔지만 서버에는 못 갔습니다. 화면을 넘기지 않고 그대로 알립니다.
      setReviewMessage(`검토 요청이 서버에 전달되지 않았습니다 — 변호사 화면에 보이지 않습니다. 다시 시도해주세요. (${sync.message})`);
      return;
    }
    setReviewMessage(result?.message || '변호사 검토 요청이 등록되었습니다.');
    if (result?.ok && onGoToDashboard) {
      setTimeout(onGoToDashboard, 1000);
    }
  };

  const requestReview = () => {
    setReviewMessage('');
    if (!selectedCase || !analysis || !onRequestLegalReview) return;
    if (!analysisSaved) {
      setReviewMessage('분석 내용을 먼저 저장한 뒤 검토 요청을 진행해주세요.');
      return;
    }
    setPendingHitlAction({ type: 'review' });
  };

  const confirmHitlAction = async () => {
    const actionType = pendingHitlAction?.type;
    setPendingHitlAction(null);
    if (actionType === 'save') await performSaveAnalysis();
    if (actionType === 'review') await performRequestReview();
  };

  return (
    <main className="workspacePage">
      <section className="workflowPanel analysisPanel">
        <WorkPageHeader
          title="실시간 상담"
          description="통화를 시작하고 메모한 뒤, 상담이 끝나면 분석하세요."
        />
        <div className="inlineControls analysisCommandBar">
          <CasePicker consultations={consultations} value={selectedId} onChange={selectCase} />
          <button type="button" className="quickStartButton" onClick={startQuickRealtimeSession} disabled={isStartingQuickSession}>
            <PhoneCall size={15} strokeWidth={2.4} /> {isStartingQuickSession ? '준비하는 중...' : '새 상담 준비'}
          </button>
          <div className="callAnalyzeButtonGroup">
            <button
              type="button"
              className={`callAnalyzeButton${analyzed ? ' done' : ''}`}
              onClick={startAnalysis}
              disabled={isAnalyzing || !selectedCase || callStatus === 'ongoing'}
            >
              {isAnalyzing ? (
                // 몇 분씩 걸리는 작업이라 경과 시간을 같이 보여줍니다 — 없으면 멈춘 것처럼 보입니다.
                `분석 중... ${formatElapsed(analysisElapsedSec)}`
              ) : analyzed ? (
                <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}><Check size={15} strokeWidth={2.4} /> 재분석 실행</span>
              ) : '분석 시작'}
            </button>
            {/* 툴팁이 아니라 항상 보이는 캡션으로 둬서, 왜 눌리지 않는지 바로 알 수 있게 합니다. */}
            {callStatus === 'ongoing' ? <small className="callAnalyzeCaption">통화 종료 후 분석 가능</small> : null}
          </div>
        </div>
        <RealtimeAnalysisPanel
          selectedCase={selectedCase}
          onUpdateConsultation={onUpdateConsultation}
          callStatus={callStatus}
          callSeconds={callSeconds}
          audioStatus={audioStatus}
          liveCaptions={liveCaptions}
          availableAudioCalls={availableAudioCalls}
          selectedAudioCallId={selectedAudioCallId}
          isLoadingAudioCalls={isLoadingAudioCalls}
          onSelectAudioCall={setSelectedAudioCallId}
          onRefreshAudioCalls={refreshAvailableAudioCalls}
          onStartCall={startCall}
          onEndCall={endCall}
          caseMeta={selectedCase ? (
            <div className="analysisCaseMeta">
              <span>사건 번호 <strong>{selectedCase.caseNo}</strong></span>
              <label className={`analysisCaseMetaEdit realtimeRequiredNameField${selectedCase.name ? '' : ' missing'}`}>
                <span>
                  {!selectedCase.name ? <AlertTriangle size={13} strokeWidth={2.4} className="realtimeRequiredNameFieldIcon" aria-hidden="true" /> : null}
                  상담받은 사람
                  {selectedCase.name
                    ? (selectedCase.nameSource === 'ai' ? <em className="nameSourceAi">AI가 찾음 · 확인해주세요</em> : null)
                    : <em>필수 입력</em>}
                </span>
                <input
                  value={selectedCase.name || ''}
                  onChange={(event) => onUpdateConsultation(selectedCase.id, {
                    name: event.target.value,
                    nameSource: 'counselor',
                  })}
                  placeholder="통화 중 이름 입력 · 분석 후 자동 정리"
                />
                {!selectedCase.name ? <small>이름은 서식 생성과 검토 요청에 쓰이니 입력해주세요.</small> : null}
                {selectedCase.name && selectedCase.nameSource === 'ai'
                  ? <small>통화 내용에서 찾은 이름입니다. 잘못 들었을 수 있으니 맞는지 봐주세요.</small>
                  : null}
              </label>
              <label className="analysisCaseMetaEdit">
                <span>상담 제목</span>
                <input
                  value={selectedCase.title || ''}
                  onChange={(event) => onUpdateConsultation(selectedCase.id, { title: event.target.value })}
                  placeholder="상담 제목 입력"
                />
              </label>
              <span>작성 시간 <strong>{selectedCase.date || '-'}{selectedCase.registeredTime ? ` ${selectedCase.registeredTime}` : ''}</strong></span>
            </div>
          ) : null}
        />
        {selectedCase ? (
          <section className="analysisResultsWorkspace" aria-label="AI 분석 결과 작업 영역">
          <div className="analysisSectionDivider">
            <span>AI 분석 결과</span>
            <p>상담 메모 · 첨부자료 기준</p>
          </div>
          {/* AI 출력은 참고용이며 최종 확정은 담당자가 수행합니다. (사람이 검토·확정하는 원칙) */}
              <div className="hitlBanner">
                <Info className="hitlBannerIcon" size={16} strokeWidth={2.4} aria-hidden="true" />
                <span>
                  <strong>AI가 정리한 내용은 참고용이에요.</strong>
                  <small>분류 · 긴급도 · 구조대상은 사람이 확정</small>
                </span>
              </div>

        {selectedCase ? (
          <div className="analysisProgressPanel">
            <span className={analyzed ? 'statusChip tone-success' : 'statusChip tone-muted'}>{analyzed ? '분석 완료' : '분석 전'}</span>
            {/* 분석 전에는 저장할 대상이 없으므로 주의색(주황) 대신 중립색으로 '저장 전'을 보여주고,
                분석을 마쳐 저장할 내용이 생겼을 때만 '저장 필요'(주황)로 주의를 끕니다. */}
            <span className={analysisSaved ? 'statusChip tone-success' : analyzed ? 'statusChip tone-warn' : 'statusChip tone-muted'}>{analysisSaved ? '저장됨' : analyzed ? '저장 필요' : '저장 전'}</span>
            <span className={selectedCase.reviewAction && !selectedCase.reviewAction.resolved ? 'statusChip tone-warn' : 'statusChip tone-info'}>
              {selectedCase.reviewAction && !selectedCase.reviewAction.resolved ? `${selectedCase.reviewAction.status} 대응` : selectedCase.workflowStatus || '상담 분석'}
            </span>
          </div>
        ) : null}
        {analyzed ? (
          <>
          <div className="resultInlineRow">
                <h3>AI 응답 검증</h3>
                <span className={`statusChip ${analysis.verification?.format ? 'tone-success' : 'tone-danger'}`}>형식 검증 {analysis.verification?.format ? '통과' : '오류'}</span>
                <span className={`statusChip ${analysis.verification?.grounded ? 'tone-success' : 'tone-warn'}`}>근거 검증 {analysis.verification?.grounded ? '첨부자료 근거 확인' : '근거 부족 (첨부자료 없음)'}</span>
                <span className={`statusChip ${analysis.verification?.hallucinationRisk ? 'tone-danger' : 'tone-success'}`}>환각 탐지 {analysis.verification?.hallucinationRisk ? '위험 - 원문 내용 부족' : '이상 없음'}</span>
              </div>
              <div className="resultInlineRow">
                <h3>받은 자료</h3>
                {/* 복원 경로가 이 필드를 안 채우면 undefined.map으로 화면이 통째로 죽습니다.
                    병합으로 모양은 맞췄지만, 그리는 쪽에서도 한 번 더 막아둡니다. */}
                {(analysis.modalities || []).map((item) => (
                  <span key={item.key} className="modalityStat">
                    <span className={`statusChip ${item.count > 0 ? 'tone-info' : 'tone-muted'}`}>{item.key}</span>
                    <strong className="modalityValue">{item.count}건</strong>
                  </span>
                ))}
              </div>
              <div className="resultInlineRow">
                <h3>자료 읽기 결과</h3>
                {analysis.extractionDetail?.length ? analysis.extractionDetail.map((item, index) => (
                  <span
                    key={`${item.fileLink}-${index}`}
                    className={`extractChip status-${item.status}`}
                    title={[item.fileLink, item.note].filter(Boolean).join(' · ')}
                  >
                    <strong>{extractionStatusLabel(item.status)}</strong>
                    <span>{item.fileLink || '(파일명 없음)'}</span>
                    {item.note ? <em>{item.note}</em> : null}
                  </span>
                )) : <span className="resultInlineEmpty">첨부파일 없음 · 메모만 분석</span>}
              </div>
          
          <div className="analysisControlBar">
            
            <div>
              <strong>AI 자동 확인</strong>
              <span>결과 확인 · 저장 · 검토 요청</span>
            </div>
            <div className="analysisActions">
              {/* 두 버튼은 하는 일이 서로 다릅니다. 색만으로 구분되지 않도록 아이콘·제목·설명을 나눠 표시합니다. */}
              <button className={`aiActionCard tone-eligibility${analysis?.aiLinked?.eligibility ? ' done' : ''}`} type="button" onClick={runEligibilityCheck}>
                <ShieldCheck size={22} strokeWidth={2.2} />
                <span>
                  <strong>무료 법률구조 대상 확인</strong>
                  <small>대상 · 증빙 · 긴급도</small>
                </span>
                {analysis?.aiLinked?.eligibility ? <em><Check size={13} strokeWidth={2.4} /> 완료</em> : null}
              </button>
              <button className={`aiActionCard tone-missing${analysis?.aiLinked?.missing ? ' done' : ''}`} type="button" onClick={runMissingDataCheck}>
                <ClipboardList size={22} strokeWidth={2.2} />
                <span>
                  <strong>누락자료 점검</strong>
                  <small>더 받아야 할 서류 찾기</small>
                </span>
                {analysis?.aiLinked?.missing ? <em><Check size={13} strokeWidth={2.4} /> 완료</em> : null}
              </button>
            </div>
          </div>
          </>
        ) : null}
        {activeReviewAction ? (
          <section className={`reviewRequestBanner tone-${reviewActionTone(activeReviewAction.status)}`}>
            <div>
              <strong>{activeReviewAction.status}</strong>
              <span>{activeReviewAction.requestedAt}</span>
            </div>
            <dl>
              <dt>작성 변호사</dt>
              <dd>
                {activeReviewAction.reviewer?.name || '변호사'}
                {activeReviewAction.reviewer?.email ? ` · ${activeReviewAction.reviewer.email}` : ''}
                {activeReviewAction.reviewer?.organization ? ` · ${activeReviewAction.reviewer.organization}` : ''}
              </dd>
            </dl>
            <SummaryBulletList text={activeReviewAction.reason} emptyText="사유 없음" />
            {activeReviewAction.lawyerComment ? <div className="reasonText"><strong>변호사 코멘트</strong><SummaryBulletList text={activeReviewAction.lawyerComment} /></div> : null}
          </section>
        ) : null}
        {/* 승인처럼 reviewAction이 남지 않는 결정에서도, 변호사가 남긴 코멘트는 계속 보이게 둡니다. */}
        {!activeReviewAction && selectedCase?.lawyerComment ? (
          <section className="reviewRequestBanner tone-success">
            <div><strong>승인 · 변호사 코멘트</strong></div>
            <SummaryBulletList text={selectedCase.lawyerComment} />
          </section>
        ) : null}
        {aiTaskMessage && (aiTaskMessage.includes('API') || aiTaskMessage.includes('실패') || aiTaskMessage.includes('연결')) ? (
          <p className="formError" role="status">{aiTaskMessage}</p>
        ) : null}
        {aiResultSummary ? (
          <section className="aiResultPanel" aria-label={aiResultSummary.title}>
            {aiTaskMessage ? (
              <div className="aiResultNotice" role="status">
                <strong>{aiTaskMessage}</strong>
                <span>확인 후 필요한 항목만 반영</span>
              </div>
            ) : null}
            <div className="aiResultHeader">
              <div>
                <h3>{aiResultSummary.title}</h3>
                <p>{aiResultSummary.description}</p>
              </div>
              <span className="statusChip tone-info">AI API 반영</span>
            </div>
            <div className="aiResultMetrics">
              {aiResultSummary.metrics.map((item) => (
                <span key={item.label}><small>{item.label}</small><strong>{item.value}</strong></span>
              ))}
            </div>
            {aiResultSummary.items.length ? (
              <ul className="aiResultList">
                {aiResultSummary.items.map((item) => <li key={item}>{item}</li>)}
              </ul>
            ) : <p className="helperText">추가 세부 항목 없음</p>}
          </section>
        ) : null}
        {!analyzed ? (
          <div className="emptyState">
            <ClipboardList size={22} strokeWidth={2.2} aria-hidden="true" />
            <p>{callStatus === 'ongoing' ? '통화가 끝나면 분석을 시작할 수 있습니다.' : (selectedCase?.memo || '').trim() ? '메모 작성 완료 · 분석을 시작하세요.' : '메모를 작성하면 분석을 시작할 수 있습니다.'}</p>
            <span className="emptyStateHint">현재 메모를 바탕으로 사건 유형과 확인할 자료를 정리합니다.</span>
            <button type="button" className="emptyStateAction callAnalyzeButton" onClick={startAnalysis} disabled={isAnalyzing || !selectedCase || callStatus === 'ongoing'}>
              {isAnalyzing ? `분석 중... ${formatElapsed(analysisElapsedSec)}` : '분석 시작'}
            </button>
          </div>
        ) : (
          <div className="workflowColumns">
            <div>
              {/* AI 출력은 참고용이며 최종 확정은 담당자가 수행합니다. (사람이 검토·확정하는 원칙) */}
              <div className="hitlBanner">
                <Info className="hitlBannerIcon" size={16} strokeWidth={2.4} aria-hidden="true" />
                <span>
                  <strong>AI가 정리한 내용은 참고용이에요.</strong>
                  <small>분류 · 긴급도 · 구조대상은 사람이 확정</small>
                </span>
              </div>
              {/* 코치 피드백 반영: AI 분석 요약(pinned) → 아코디언 그룹(부수적인 세부 내용,
                  무료 법률구조 대상 검토 포함) → 체크리스트(pinned)를 맨 마지막에 두는
                  '북엔드' 순서로 정리합니다. 펼쳐 고정된 섹션이 앞뒤로 하나씩만 있고
                  가운데는 전부 아코디언이라 섞여 보이지 않습니다. */}
              {/* 같은 화면의 다른 요소들('AI 자동 확인', 'AI 응답 검증' 등)은 모두 줄임말 'AI'를
                  쓰는데 이 제목만 '인공지능'으로 풀어 써서 표기가 튀었습니다. 맞춥니다. */}
              <CollapsibleSection icon={Sparkles} title="AI 분석 요약" pinned confirmed={Boolean(confirmedSections.summary)} onToggleConfirm={() => toggleSectionConfirmed('summary')}>
                <div className="resultCard"><SummaryBulletList text={analysis.summary} /></div>
              </CollapsibleSection>
              <CollapsibleSection icon={Inbox} title="받은 자료" confirmed={Boolean(confirmedSections.modalities)} onToggleConfirm={() => toggleSectionConfirmed('modalities')}>
                <div className="resultCard">
                  {/* 복원 경로가 이 필드를 안 채우면 undefined.map으로 화면이 통째로 죽습니다.
                      병합으로 모양은 맞췄지만, 그리는 쪽에서도 한 번 더 막아둡니다. */}
                  {(analysis.modalities || []).map((item) => <span key={item.key} className="miniField" style={{ marginRight: 12 }}>{item.key}: {item.count}건</span>)}
                </div>
              </CollapsibleSection>
              <CollapsibleSection icon={FileSearch} title="자료 읽기 결과" confirmed={Boolean(confirmedSections.extraction)} onToggleConfirm={() => toggleSectionConfirmed('extraction')}>
                <div className="resultCard">
                  {analysis.extractionDetail?.length ? analysis.extractionDetail.map((item, index) => (
                    <div key={`${item.fileLink}-${index}`} className="extractRow">
                      <span className={`extractStatus status-${item.status}`}>{extractionStatusLabel(item.status)}</span>
                      <span className="extractName"><Paperclip size={12} strokeWidth={2.4} aria-hidden="true" /> {item.fileLink || '(파일명 없음)'}</span>
                      <span className="extractNote">{item.note}</span>
                    </div>
                  )) : <p>첨부파일 없음 · 메모만 분석</p>}
                </div>
              </CollapsibleSection>
              <CollapsibleSection icon={EyeOff} title="개인정보는 자동으로 가려집니다" confirmed={Boolean(confirmedSections.stt)} onToggleConfirm={() => toggleSectionConfirmed('stt')}>
                <div className="resultCard">
                  <div className="segmented compactSegmented">
                    <button type="button" className={showMaskedStt ? 'active' : ''} onClick={() => setShowMaskedStt(true)}>개인정보 가림</button>
                    <button type="button" className={!showMaskedStt ? 'active' : ''} onClick={() => setShowMaskedStt(false)}>원문</button>
                  </div>
                  {!showMaskedStt ? <p className="sensitiveSourceNotice">민감정보 포함 가능 · 검증 시에만 확인</p> : null}
                  <p className="sttPreviewText">{showMaskedStt ? analysis.sttPreview?.masked : analysis.sttPreview?.original}</p>
                  <p className="helperText">기본값: 개인정보 가림 · 원문: 오류 확인용</p>
                </div>
              </CollapsibleSection>
              <CollapsibleSection icon={BadgeCheck} title="AI 응답 검증" confirmed={Boolean(confirmedSections.verification)} onToggleConfirm={() => toggleSectionConfirmed('verification')}>
                <div className="resultCard">
                  <span className="miniField">형식 검증: {analysis.verification?.format ? '통과' : '오류'}</span>
                  <span className="miniField">근거 검증: {analysis.verification?.grounded ? '첨부자료 근거 확인' : '근거 부족 (첨부자료 없음)'}</span>
                  <span className="miniField">환각 탐지: {analysis.verification?.hallucinationRisk ? '위험 - 원문 내용 부족' : '이상 없음'}</span>
                </div>
              </CollapsibleSection>
              <CollapsibleSection icon={Scale} title="무료 법률구조 대상 검토" confirmed={Boolean(confirmedSections.eligibility)} onToggleConfirm={() => toggleSectionConfirmed('eligibility')}>
              <div className={analysis.aiLinked?.eligibility ? 'resultCard aiLinkedCard' : 'resultCard'}>
                {analysis.aiLinked?.eligibility ? (
                  <div className="fieldSyncNotice">
                    <strong>무료 법률구조 대상 확인 결과 반영됨</strong>
                    <span>대상 · 증빙 · 긴급도 · 체크리스트 갱신</span>
                  </div>
                ) : null}
                <label className="miniField">사건 유형<input value={analysis.caseType} onChange={(event) => setAnalysis({ ...analysis, caseType: event.target.value })} /></label>
                <p className="reasonText">분류 근거: {analysis.caseTypeReason}</p>
                <label className="miniField">긴급도 등급
                  <select value={analysis.urgency} onChange={(event) => setAnalysis({ ...analysis, urgency: event.target.value, emergency: { ...analysis.emergency, level: event.target.value } })}><option>상</option><option>중</option><option>하</option></select>
                </label>
                {/* 예전엔 이 자리에 그라디언트 막대(게이지)와 점수를 함께 보여줬는데, 막대와
                    숫자를 같이 보는 게 불편하다는 피드백에 따라 막대를 걷어내고 등급 배지 +
                    점수 숫자만 남깁니다(위 select의 상/중/하와 같은 값을 배지로도 확인). */}
                <div className="urgencyGauge">
                  <span className={`statusChip tone-${{ 상: 'danger', 중: 'warn', 하: 'success' }[analysis.emergency?.level] || 'muted'}`}>긴급도 {analysis.emergency?.level || '미확인'}</span>
                  <span className="urgencyGaugeValue">점수 {Math.round((analysis.emergency?.ratio || 0) * 100)}점</span>
                </div>
                <hr />
                <div className="fieldPairRow">
                  {analysis.eligibilityCheck ? (
                    <div className={analysis.eligibilityCheck.isTargetCandidate && !analysis.eligibilityCheck.evidenceSubmitted ? 'eligibilitySummary missingEvidence' : 'eligibilitySummary'}>
                      <span>대상 유형: {analysis.eligibilityCheck.applicantType}</span>
                      <span>필요 증빙: {analysis.eligibilityCheck.requiredEvidence}</span>
                      <span>증빙 제출: {analysis.eligibilityCheck.evidenceSubmitted ? '확인됨' : '미제출'}</span>
                    </div>
                  ) : <div />}
                  <label className="miniField">무료 법률구조 대상<select value={analysis.eligibility} onChange={(event) => setAnalysis({ ...analysis, eligibility: event.target.value })}><option>검토 필요</option><option>구조 가능</option><option>부적합</option><option>보류</option></select></label>
                </div>
              </div>
              </CollapsibleSection>
              {analysis.reliefReviewDetail ? (
                <CollapsibleSection icon={ListChecks} title="체크리스트 AI 분석 상세" confirmed={Boolean(confirmedSections.reliefDetail)} onToggleConfirm={() => toggleSectionConfirmed('reliefDetail')}>
                  <div className="resultCard">
                    <ReliefReviewDetailTabs detail={analysis.reliefReviewDetail} />
                  </div>
                </CollapsibleSection>
              ) : null}
              <CollapsibleSection icon={Sparkles} title="체크리스트 AI 분석 결과" confirmed={Boolean(confirmedSections.reliefResult)} onToggleConfirm={() => toggleSectionConfirmed('reliefResult')}>
                <div className="resultCard">
                  {analysis.reliefReviewDetail ? (
                    <ReliefLawyerSummaryCard detail={analysis.reliefReviewDetail} />
                  ) : (
                    <InlineEmptyNotice>AI 분석 결과 없음 · 분석을 다시 실행하세요</InlineEmptyNotice>
                  )}
                </div>
              </CollapsibleSection>
              <CollapsibleSection icon={ListChecks} title="체크리스트" pinned confirmed={Boolean(confirmedSections.checklist)} onToggleConfirm={() => toggleSectionConfirmed('checklist')}>
                <div className="resultCard checklistBox">
                  {(analysis.checklist || []).map((item, index) => {
                    const note = checklistItemNote(item, analysis.reliefReviewDetail);
                    const flag = checklistItemFlag(item, analysis.reliefReviewDetail);
                    return (
                      <div className={`checklistItem${item.checked ? ' is-checked' : ''}`} key={item.label}>
                        <label>
                          <input type="checkbox" checked={item.checked} onChange={() => updateChecklist(index)} />
                          {item.checked ? <Check size={14} strokeWidth={2.4} className="checklistItemCheckIcon" aria-hidden="true" /> : <span className="checklistItemCheckIcon checklistItemCheckIconEmpty" aria-hidden="true" />}
                          {item.label}
                        </label>
                        {note ? <p className="checklistItemNote">{note}</p> : null}
                        {flag ? <span className={`statusChip ${flag.tone}`}>{flag.text}</span> : null}
                      </div>
                    );
                  })}
                </div>
              </CollapsibleSection>
            </div>
            <div className="analysisActionRail">
              {/* '검토 조치 패널 / 필요 항목만 채택' 안내 카드는 없앴습니다 — 아래 네 섹션이
                  이미 아이콘+제목으로 각자 무엇을 하는지 보여주고, "필요 항목만 채택"이
                  전달하려던 메시지도 AI 추천 후속 작업 섹션의 안내문("채택한 항목만
                  검토에 반영")에 그대로 남아 있어 정보 손실 없이 자리만 절약합니다. */}
              {/* 누락자료 확인 → AI 추천 채택 → 반영 항목의 3단계가 구분선 없이 이어지면
                  하나의 목록처럼 섞여 보여서, 단계마다 소제목 아래 구분선을 둬 눈으로도
                  단계가 갈라지게 합니다. */}
              {/* 코치 피드백("가장 유용한 부분은 아코디언을 하지 않는 게 어떨까요")에 따라, 이
                  목록은 상담원이 실제로 챙겨야 할 가장 중요한 항목이라 아예 접고 펴는 동작을
                  없애 항상 펼친 상태로 고정합니다(pinned). 배지는 그대로 두어 미제출 건수를
                  다른 보조 섹션과 시각적으로 구분합니다. */}
              <CollapsibleSection
                icon={Paperclip}
                title="누락 자료 확인"
                className="railSection railSection-important"
                pinned
                badge={<span className="statusChip tone-warn">{(analysis.missingInfo || []).filter((item) => analysis.evidenceStatus?.[item] !== 'submitted').length}건 미제출</span>}
                confirmed={Boolean(confirmedSections.missingInfo)}
                onToggleConfirm={() => toggleSectionConfirmed('missingInfo')}
              >
                <p className="railHint">자료를 받으면 ‘제출’로 변경</p>
                {analysis.aiLinked?.missing ? (
                  <p className="fieldSyncNotice compactNotice"><strong>누락자료 반영됨</strong><span>보완 자료 목록 갱신</span></p>
                ) : null}
                <div className={analysis.aiLinked?.missing ? 'scrollBox small noCap aiLinkedList' : 'scrollBox small noCap'}>
                  {(analysis.missingInfo || []).length ? analysis.missingInfo.map((item) => {
                    const submitted = analysis.evidenceStatus?.[item] === 'submitted';
                    return (
                      <button type="button" key={item} className={`evidenceItem ${submitted ? 'submitted' : 'missing'}`} onClick={() => toggleEvidenceStatus(item)} aria-pressed={submitted}>
                        <span className="evidenceItemName">{item}</span>
                        <span className="evidenceItemState">{submitted ? '제출' : '미제출'}</span>
                      </button>
                    );
                  }) : <p>누락 자료 없음</p>}
                </div>
              </CollapsibleSection>
              {/* 누락 자료 확인은 상담 진행 중 바로바로 체크해야 하는 핵심 목록이라 스크롤
                  박스로 계속 보이게 두고, AI 추천 후속 작업은 참고용 제안 목록이라 평소엔
                  접어 두고 필요할 때만 펼치는 아코디언으로 둡니다. */}
              <CollapsibleSection icon={Sparkles} title="AI 추천 후속 작업" className="railSection" confirmed={Boolean(confirmedSections.suggestions)} onToggleConfirm={() => toggleSectionConfirmed('suggestions')}>
                <p className="railHint">채택한 항목만 검토에 반영</p>
                <div className="scrollBox noCap">
                  {suggestions.map((item) => {
                    const picked = chosen.includes(item.label);
                    return (
                      <button className={`adoptButton${picked ? ' picked' : ''}`} type="button" key={item.label} onClick={() => setChosen((current) => current.includes(item.label) ? current : [...current, item.label])} disabled={picked}>
                        <span className="adoptText"><strong>{item.label}</strong><small>{item.description}</small></span>
                        <strong className="adoptAction">{picked ? '채택됨' : '채택'}</strong>
                      </button>
                    );
                  })}
                </div>
              </CollapsibleSection>
              {/* 예전엔 '검토 반영 항목'이 위아래 두 군데에 같은 chosen 목록을 그대로
                  중복 렌더링하고 있었습니다(복사 과정에서 생긴 실수로 보임) — 라벨만 다르고
                  내용·동작은 완전히 같아 자리만 두 배로 차지했습니다. 하나로 합칩니다.
                  이 목록과 타임라인은 대부분 비어 있는 채로 쓰이는 보조 정보라 접어 두고,
                  펼치지 않아도 몇 건인지는 배지로 바로 보이게 합니다. */}
              <CollapsibleSection icon={ListChecks} title="검토 반영 항목" className="railSection" badge={<span className="statusChip tone-muted">{chosen.length}건</span>} confirmed={Boolean(confirmedSections.chosenItems)} onToggleConfirm={() => toggleSectionConfirmed('chosenItems')}>
                <div className="scrollBox small noCap chosenBox">{chosen.length ? chosen.map((item) => (
                  <button type="button" key={item} onClick={() => setChosen(chosen.filter((value) => value !== item))}>
                    <span className="chosenItemName">{item}</span>
                    <em className="chosenItemDrop">제외</em>
                  </button>
                )) : <p>채택 항목 없음</p>}</div>
              </CollapsibleSection>
              <CollapsibleSection icon={Clock} title="사실관계 타임라인" className="railSection" badge={<span className="statusChip tone-muted">{(analysis.timeline || []).length}건</span>} confirmed={Boolean(confirmedSections.timeline)} onToggleConfirm={() => toggleSectionConfirmed('timeline')}>
                <div className="scrollBox small noCap">
                  {/* 없을 때 안내를 보여주는 건 master 쪽 동작을 그대로 살리고,
                      timeline이 아예 undefined인 경우(복원 경로)에도 죽지 않게 감쌉니다. */}
                  {(analysis.timeline || []).length
                    ? analysis.timeline.map((item, index) => <button type="button" key={`${item.date}-${index}`}>{item.date} - {item.text}</button>)
                    : <InlineEmptyNotice>{timelineEmptyMessage(analysis.timelineIssue)}</InlineEmptyNotice>}
                </div>
                <div className="inlineControls compactInline">
                  <input value={timelineText} onChange={(event) => setTimelineText(event.target.value)} placeholder="타임라인 항목" />
                  <button type="button" onClick={() => {
                    if (!timelineText.trim()) return;
                    setAnalysis({ ...analysis, timeline: [...(analysis.timeline || []), { date: today, text: timelineText }] });
                    setTimelineText('');
                  }}>추가</button>
                </div>
              </CollapsibleSection>
            </div>
          </div>
        )}
        {analyzed ? (
          <RecommendedFormsPanel
            selectedCase={selectedCase}
            onOpenDraft={onOpenDraft}
            onSaveBeforeOpen={saveThenOpenDraft}
            saving={savingBeforeDraft}
          />
        ) : null}
        {analyzed ? (
          <div className="analysisFinalActions">
            <button className="primaryButton compactAction" type="button" onClick={saveAnalysis}>분석 내용 저장</button>
            <button className="secondaryActionButton compactAction" type="button" onClick={requestReview} disabled={!analysisSaved}>변호사 검토 요청</button>
          </div>
        ) : null}
          </section>
        ) : null}
        {savedMessage ? (
          <p className={savedMessage.startsWith('저장 실패') ? 'formError' : 'successBanner'} role="status">
            {savedMessage.startsWith('저장 실패') ? null : <span className="successBannerBadge"><CheckCircle2 size={12} strokeWidth={2.4} aria-hidden="true" />저장 완료</span>}
            {savedMessage.replace(/^저장 (완료|실패): /, '')}
          </p>
        ) : null}
        {reviewMessage ? (
          <p className={reviewMessage.includes('찾을 수') || reviewMessage.includes('먼저 저장') ? 'formError' : 'successBanner'} role="status">
            {reviewMessage.includes('찾을 수') || reviewMessage.includes('먼저 저장') ? null : <span className="successBannerBadge"><CheckCircle2 size={12} strokeWidth={2.4} aria-hidden="true" />요청 완료</span>}
            {reviewMessage}
          </p>
        ) : null}
        {pendingHitlAction ? (
          <HitlConfirmModal
            title={pendingHitlAction.type === 'save' ? '상담 분석 저장 전 최종 확인' : '변호사 검토 요청 전 최종 확인'}
            actionLabel={pendingHitlAction.type === 'save' ? '확인 후 저장' : '확인 후 요청'}
            caseInfo={caseInfoText}
            onConfirm={confirmHitlAction}
            onCancel={() => setPendingHitlAction(null)}
          />
        ) : null}
      </section>
    </main>
  );
}

function DraftWorkbench({ consultations, currentUser, role, onUpdateConsultation, onNotify, focusedConsultationId, focusedTemplateName }) {
  const showToast = useToast();
  const [step, setStep] = useState('select');
  // 분석 화면에서 '초안 만들기'로 넘어오면 focusedConsultationId가 그 사건을 가리킵니다.
  // 처음에 목록 첫 사건으로 시작한 뒤 아래 useEffect가 교정하는 방식이었는데, 그러면
  // 첫 렌더에서 엉뚱한 사건으로 추천 API를 한 번 부르고 나서 다시 부릅니다.
  // 넘어올 때마다 추천이 다시 도는 것처럼 보이던 게 이것 때문입니다.
  const [caseId, setCaseId] = useState(() => focusedConsultationId || caseOptions(consultations)[0].id);
  const [template, setTemplate] = useState(null);
  const [draft, setDraft] = useState('');
  const [savedMessage, setSavedMessage] = useState('');
  const [generatedFileMessage, setGeneratedFileMessage] = useState('');
  const [favorites, setFavorites] = useState(() => getFavoriteTemplates());
  const selectedCase = consultations.find((item) => String(item.id) === String(caseId));
  const runWithLoading = useAsyncAction();
  const canUseCoreApi = Boolean(selectedCase?.coreId && selectedCase?.coreAnalysisId);

  useEffect(() => {
    if (!focusedConsultationId) return;
    const focusedCase = consultations.find((item) => String(item.id) === String(focusedConsultationId));
    if (focusedCase) {
      setCaseId(focusedCase.id);
      setStep('select');
    }
  }, [focusedConsultationId, consultations]);

  // '추천 서식' 목록에서 특정 서식의 '저장하고 초안 만들기'를 눌러 들어오면, 어떤 서식을
  // 눌렀는지와 상관없이 항상 같은(초기) 서식으로 열려 있었습니다(코치 피드백: 3개 추천
  // 버튼이 다 똑같이 동작). 눌렀던 서식을 그대로 선택된 채로 열어 줍니다.
  const appliedFocusTemplateRef = useRef(null);
  useEffect(() => {
    if (!focusedTemplateName || appliedFocusTemplateRef.current === focusedTemplateName) return;
    appliedFocusTemplateRef.current = focusedTemplateName;
    setTemplate(focusedTemplateName);
  }, [focusedTemplateName]);

  // 아직 core-api에 상담/분석이 저장되지 않은 사건(로컬 프로토타입 진행 중)이면, 초안을 실제로
  // 생성하기 직전에 한 번 밀어 넣습니다. 이미 저장돼 있으면(canUseCoreApi) 그대로 씁니다.
  const syncCaseForDraftGeneration = async () => {
    if (!selectedCase) return null;
    const analysis = selectedCase.analysis || buildAnalysisResult(selectedCase);
    let coreId = selectedCase.coreId || '';
    let coreAnalysisId = selectedCase.coreAnalysisId || '';
    let coreSync = null;

    if (!coreId) {
      coreSync = await createCoreConsultation({ currentUser: { ...currentUser, role: currentUser?.role || role }, consultation: selectedCase });
      coreId = coreSync?.coreId || '';
    }

    if (!coreAnalysisId && coreId) {
      const savedAnalysis = await createCoreAnalysis({ consultation: { ...selectedCase, ...(coreSync || {}), coreId }, analysis });
      coreAnalysisId = savedAnalysis?.analysis_id || '';
    }

    if (coreId || coreAnalysisId) {
      onUpdateConsultation?.(selectedCase.id, {
        ...(coreSync || {}),
        coreId,
        coreAnalysisId,
        analysis,
      });
    }

    return coreId && coreAnalysisId ? { coreId, coreAnalysisId, analysis } : null;
  };

  // ── 서식 추천 실연동: coreId·분석id가 있는 사건은 core-api → ai-api 추천 결과를 받아옵니다.
  // 없으면(로컬 상담이거나 core-api 저장 실패) 기존 로컬 휴리스틱(recommendTemplates)으로 조용히 대체합니다.
  // 분석 화면과 같은 훅을 씁니다. 저장된 recommendation_json이 있으면 그걸 쓰고,
  // 없으면 이번 세션 캐시를, 그것도 없으면 API를 부릅니다.
  const { aiRecommendations, loading: recommendLoading } = useFormRecommendations(selectedCase);

  // ── 생성된 초안의 core-api 문서 상태(초안 생성 → 검토 요청 → 승인/반려)입니다.
  // 사건이나 서식을 바꾸면 이전 초안의 id가 지금 화면과 안 맞으니 초기화합니다.
  const [draftDocument, setDraftDocument] = useState(null);
  const [submitReviewPending, setSubmitReviewPending] = useState(false);
  useEffect(() => {
    setDraftDocument(null);
  }, [caseId, template]);

  // 사건에 제출된 서식 초안 목록입니다. 변호사는 이 목록으로 내부 검토를 하고, 상담원은
  // 같은 목록을 읽기 전용으로 보며 검토 상태·변호사 코멘트·수정본 여부를 확인합니다.
  const isLawyerReviewer = role === 'lawyer';
  const [caseDocuments, setCaseDocuments] = useState([]);
  const [documentsLoading, setDocumentsLoading] = useState(false);
  const reloadCaseDocuments = () => {
    if (!selectedCase?.coreId) {
      setCaseDocuments([]);
      return;
    }
    setDocumentsLoading(true);
    fetchCoreDocuments(selectedCase.coreId)
      .then((list) => setCaseDocuments((list || []).map((document) => hydrateDraftDocument(document, {
        consultationId: selectedCase.coreId,
        caseNo: selectedCase.caseNo,
      }))))
      .catch(() => setCaseDocuments([]))
      .finally(() => setDocumentsLoading(false));
  };
  useEffect(() => {
    reloadCaseDocuments();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedCase?.coreId]);

  // 변호사 내부 검토 인라인 폼 상태. 한 번에 하나의 문서만 검토 폼을 열어둡니다.
  const [reviewingDocumentId, setReviewingDocumentId] = useState(null);
  const [reviewNoteText, setReviewNoteText] = useState('');
  const [reviewPending, setReviewPending] = useState(false);
  // 서식 초안 직접 편집. core-api 문서는 서버 원본을 다시 만들 API가 없어, 편집 결과는
  // 이 브라우저에 '변호사 수정본'으로 남겨 상담원 화면에도 함께 보여줍니다.
  const [reviewContentDraft, setReviewContentDraft] = useState('');
  const startDocumentReview = (doc) => {
    setReviewingDocumentId(doc.document_id);
    setReviewNoteText('');
    setReviewContentDraft(readLawyerDraftEdit(doc.document_id)?.content || doc.draft_content || '');
  };
  const cancelDocumentReview = () => {
    setReviewingDocumentId(null);
  };
  const confirmDocumentReview = async (doc) => {
    if (!selectedCase?.coreId || !reviewingDocumentId) return;
    setReviewPending(true);
    try {
      // 승인 요청이 실패해도(예: 권한 없음) 변호사가 고친 내용은 이 브라우저에 먼저 남겨
      // 작업이 사라지지 않게 합니다.
      if (reviewContentDraft.trim() !== (doc.draft_content || '').trim()) {
        saveLawyerDraftEdit(reviewingDocumentId, reviewContentDraft);
      }
      const token = currentUser?.token;
      await approveCoreDocument(selectedCase.coreId, reviewingDocumentId, reviewNoteText, token);
      showToast('서식 초안 내부 검토를 완료했습니다.', 'success');
      setReviewingDocumentId(null);
      reloadCaseDocuments();
    } catch (error) {
      showToast(`처리에 실패했습니다: ${friendlyErrorMessage(error, '잠시 후 다시 시도해 주세요.')}`, 'warn');
    } finally {
      setReviewPending(false);
    }
  };

  // 이 사건의 확정 사건 분류입니다. 서식 추천과 초안 본문이 같은 값을 쓰도록 한 곳에서만 정합니다.
  // (소분류 우선 → 대분류 → 등록 때 고른 유형 순서는 resolveConfirmedCaseType 참고)
  const draftCaseType = resolveConfirmedCaseType(selectedCase);

  // 서식이 291개로 많아졌기 때문에, 대분류 탭 → 소분류 드롭다운 → 서식명 검색 3단계로 좁혀서 보여줍니다.
  const [majorFilter, setMajorFilter] = useState('전체');
  const [minorFilter, setMinorFilter] = useState('전체');
  const [searchText, setSearchText] = useState('');
  // 선택한 사건의 확정 분류에 맞는 서식만 볼지 여부. 291개를 매번 손으로 좁히지 않아도 되게 합니다.
  // 코치 피드백(직접 화면 확인): 이 토글이 기본 꺼짐이라, 정작 처음 들어오면 291개를 필터 없이
  // 그대로 보여줬습니다. 사건 분류를 이미 아는 경우 기본으로 켜서, 화면을 열자마자 좁혀진
  // 목록부터 보이게 합니다(분류를 모르는 사건이면 scopeToCase가 자동으로 꺼진 것과 같게 동작).
  const [onlyForCase, setOnlyForCase] = useState(true);
  const activeMajor = caseCategories.find((category) => category.key === majorFilter);
  const minorOptions = ['전체', ...(activeMajor ? activeMajor.subTypes : [])];

  // 켜둔 채로 분류가 없는 사건으로 넘어가면 목록이 빈 채로 잠기므로, 실제 적용 여부는 분류 유무까지 함께 봅니다.
  const scopeToCase = onlyForCase && Boolean(draftCaseType);
  // 추천 목록을 켜면 그 결과를, 끄면 전체 서식을 바탕으로 아래 3단계 필터를 겁니다.
  const baseTemplates = scopeToCase ? recommendTemplates(draftCaseType) : legalTemplateSeed;

  const filteredTemplates = baseTemplates.filter((item) => {
    const matchesMajor = majorFilter === '전체' || item.caseCategory === majorFilter;
    const matchesMinor = minorFilter === '전체' || item.caseType === minorFilter;
    const matchesSearch = !searchText.trim() || item.templateName.includes(searchText.trim());
    return matchesMajor && matchesMinor && matchesSearch;
  });
  // AI 추천(recommend-forms) 결과가 있으면 즐겨찾기보다도 먼저 보여줍니다 — 지금 이 사건에
  // 대해 실제로 추천된 서식이라 가장 눈에 잘 띄어야 합니다. rank가 있으면 그 순서를 따릅니다.
  const aiRecommendationRank = new Map(aiRecommendations.map((item, index) => [item.form_name, item.rank ?? index]));
  const templates = [...filteredTemplates].sort((a, b) => {
    const aRank = aiRecommendationRank.has(a.templateName) ? aiRecommendationRank.get(a.templateName) : Infinity;
    const bRank = aiRecommendationRank.has(b.templateName) ? aiRecommendationRank.get(b.templateName) : Infinity;
    if (aRank !== bRank) return aRank - bRank;
    const aFav = favorites.includes(a.templateName) ? 0 : 1;
    const bFav = favorites.includes(b.templateName) ? 0 : 1;
    return aFav - bFav;
  });
  const selectedTemplate = templates.find((item) => item.templateName === template) || templates[0];

  // 상담/분석에서 추출된 값을 서식 필드에 자동 매핑하고, 값이 없는 항목은 '누락'으로 표시합니다.
  const extractedFieldMap = {
    '당사자 정보': selectedCase?.name ? `상담자: ${selectedCase.name}` : '',
    '청구 취지': draftCaseType ? `${draftCaseType} 관련 청구` : '',
    '관련 사실관계': selectedCase?.memo || selectedCase?.analysis?.summary || '',
    '첨부 증빙자료': selectedCase?.attachments?.length ? `${selectedCase.attachments.length}건 첨부` : '',
  };
  const draftFields = (selectedTemplate?.requiredFields || []).map((field) => ({
    field,
    value: extractedFieldMap[field] || '',
    filled: Boolean(extractedFieldMap[field]),
  }));

  const buildDraftContent = () => (
    draft || generateDraftText({
      templateName: selectedTemplate?.templateName,
      consultation: selectedCase,
      analysis: selectedCase?.analysis,
      caseType: draftCaseType,
    })
  );

  const syncDraftSnapshot = (document, draftContent) => {
    if (!document || !draftContent) return;
    rememberDraftDocumentSnapshot({
      consultation: selectedCase,
      document,
      draftContent,
    });
  };

  const handleToggleFavorite = (templateName, event) => {
    event.stopPropagation();
    setFavorites(toggleFavoriteTemplate(templateName));
  };

  // 실제 HWPX 초안은 core-api가 생성한 GeneratedDocument만 사용합니다.
  const generateDraftDocument = async (draftContent) => {
    const hwpxTemplateName = resolveHwpxTemplateName(selectedTemplate.templateName);
    const coreContext = canUseCoreApi
      ? { coreId: selectedCase.coreId, coreAnalysisId: selectedCase.coreAnalysisId }
      : await syncCaseForDraftGeneration();

    if (!coreContext) throw new Error('상담 또는 분석 결과를 Core API에 저장하지 못했습니다.');

    const created = await generateCoreDraft(coreContext.coreId, coreContext.coreAnalysisId, hwpxTemplateName);
    const document = normalizeGeneratedDocument(created);
    if (!document.documentId || !document.consultationId) {
      throw new Error('Core API 응답에 다운로드용 문서 ID가 없습니다.');
    }
    return { ...document, draftContent };
  };

  const goToPreview = async () => {
    if (!selectedTemplate) return;
    await runWithLoading(async () => {
      // 화면에 보여줄 편집 가능한 미리보기는 로컬에서 만듭니다(서버 응답은 편집 가능한
      // 텍스트가 아니라 파일 경로만 주기 때문). core-api 연동이 가능한 사건이면, 그와 별도로
      // 실제 초안 문서 레코드(documentId)를 만들어 검토 요청 흐름의 기준으로 삼습니다.
      const nextDraft = buildDraftContent();
      try {
        const document = await generateDraftDocument(nextDraft);
        setDraftDocument(document);
        syncDraftSnapshot(document, nextDraft);
        setGeneratedFileMessage(document.documentId
          ? isHwpxTemplateAlias(selectedTemplate.templateName)
            ? `HWPX 생성 완료 · 원본명 ${resolveHwpxTemplateName(selectedTemplate.templateName)}`
            : 'HWPX 생성 완료'
          : 'HWPX 생성 완료 · 파일 경로 없음');
      } catch (error) {
        setDraftDocument(null);
        const message = draftGenerationErrorMessage(error);
        setGeneratedFileMessage(message);
        showToast(message, 'warn');
      }
      setDraft(nextDraft);
      setSavedMessage('');
      setStep('draft');
    }, '서식 초안을 생성하고 있습니다');
  };

  const regenerateDraftDocument = async () => {
    if (!selectedTemplate) return;
    await runWithLoading(async () => {
      const nextDraft = buildDraftContent();
      try {
        const document = await generateDraftDocument(nextDraft);
        setDraftDocument(document);
        syncDraftSnapshot(document, nextDraft);
        setGeneratedFileMessage(document.documentId
          ? isHwpxTemplateAlias(selectedTemplate.templateName)
            ? `HWPX 재생성 완료 · 원본명 ${resolveHwpxTemplateName(selectedTemplate.templateName)}`
            : 'HWPX 재생성 완료'
          : 'HWPX 재생성 완료 · 파일 경로 없음');
        showToast('HWPX 재생성 완료', 'success');
      } catch (error) {
        setDraftDocument(null);
        const message = draftGenerationErrorMessage(error);
        setGeneratedFileMessage(message);
        showToast(message, 'warn');
      }
    }, 'HWPX 초안을 다시 생성하고 있습니다');
  };

  // 상담원: 변호사에게 검토 요청. documentId가 있어야(core-api에 실제 초안이 저장돼 있어야) 부를 수 있습니다.
  const requestDocumentReview = async () => {
    const consultationId = selectedCase?.coreId || draftDocument?.consultationId;
    if (!draftDocument?.documentId || !consultationId) return;
    if (submitReviewPending) return;
    setSubmitReviewPending(true);
    try {
      if (draftDocument.source !== 'core-api') {
        throw new Error('서버에 저장된 HWPX 초안만 검토 요청할 수 있습니다.');
      }
      const updated = await submitCoreDocumentForReview(consultationId, draftDocument.documentId);
      const normalized = normalizeGeneratedDocument(updated);
      setDraftDocument(normalized);
      syncDraftSnapshot(normalized, draft);
      onNotify?.({
        roles: 'lawyer',
        title: '서식 검토 요청',
        message: `${selectedCase.caseNo} · ${draftDocument.formName || selectedTemplate?.templateName || '서식 초안'}`,
        target: selectedCase.caseNo,
        view: '대시보드',
      });
      showToast('변호사 검토 요청 완료', 'success');
    } catch (error) {
      showToast(`검토 요청에 실패했습니다: ${friendlyErrorMessage(error, '잠시 후 다시 시도해 주세요.')}`, 'warn');
    } finally {
      setSubmitReviewPending(false);
    }
  };

  const canRequestDocumentReview = Boolean(draftDocument?.documentId) && draftDocument?.source === 'core-api' && role !== 'lawyer'
    && draftDocument.status !== 'SUBMITTED_FOR_REVIEW'
    && draftDocument.status !== 'APPROVED';
  const reviewRequestGuide = !draftDocument?.documentId
    ? 'HWPX 생성 후 요청 가능'
    : draftDocument.status === 'SUBMITTED_FOR_REVIEW'
      ? '이미 검토 요청됨'
      : draftDocument.status === 'APPROVED'
        ? '이미 승인됨'
        : '';

  // 저장 버튼이 메시지만 띄우고 실제로는 아무것도 남기지 않으면,
  // 사용자는 저장된 줄 알고 화면을 떠났다가 초안을 잃습니다. 브라우저 저장소에 실제로 남깁니다.
  const saveDraft = () => {
    if (!selectedTemplate) return;
    const entry = {
      id: `${selectedCase?.id || 'no-case'}::${selectedTemplate.templateName}`,
      caseNo: selectedCase?.caseNo || '',
      caseTitle: selectedCase?.title || '',
      templateName: selectedTemplate.templateName,
      draft,
      savedAt: new Date().toISOString(),
    };
    const saved = readStorage(storageKeys.generatedDocuments, []);
    writeStorage(storageKeys.generatedDocuments, [entry, ...saved.filter((item) => item.id !== entry.id)]);
    syncDraftSnapshot(draftDocument, draft);
    const message = `「${selectedTemplate.templateName}」 초안 저장 완료`;
    setSavedMessage(message);
    // 저장 버튼 아래 안내 문구는 스크롤 위치에 따라 안 보일 수 있습니다.
    // 눌렀다는 걸 바로 알 수 있도록 화면 우측 아래 토스트로도 같이 띄웁니다.
    showToast(message, 'success');
  };

  if (step === 'draft') {
    return (
      <main className="workspacePage">
        <section className="workflowPanel draftPanel">
          <h2><FileText size={18} strokeWidth={2.2} className="sectionIcon" aria-hidden="true" /> 서식 초안</h2>
          <div className="draftPreviewHeader">
            <div>
              <strong>{selectedTemplate?.templateName || '선택 서식'}</strong>
              <span>{selectedCase?.caseNo || '-'} · {selectedCase?.title || '상담 미선택'}</span>
            </div>
            {draftDocument?.status ? (
              <span className={`statusChip tone-${documentStatusTone(draftDocument.status)}`}>
                {DOCUMENT_STATUS_LABEL[draftDocument.status] || draftDocument.status}
              </span>
            ) : (
              <span className="statusChip tone-info">HWPX 생성 연동 준비</span>
            )}
          </div>
          <div className="scrollBox">
            <textarea className="draftEditor" value={draft} onChange={(e) => setDraft(e.target.value)} />
          </div>
          <div className="draftFinalActions">
            <button className="ghostActionButton compactAction" type="button" onClick={() => setStep('select')}>서식 선택으로 돌아가기</button>
            <button className="primaryButton compactAction" type="button" onClick={saveDraft}>서식 내용 저장</button>
            <button
              className="secondaryActionButton compactAction"
              type="button"
              onClick={requestDocumentReview}
              disabled={submitReviewPending || !canRequestDocumentReview}
              title={reviewRequestGuide || undefined}
            >
              <Send size={13} strokeWidth={2.4} aria-hidden="true" /> {submitReviewPending ? '검토 요청하는 중…' : draftDocument?.status === 'SUBMITTED_FOR_REVIEW' ? '검토 요청됨' : '변호사 검토 요청'}
            </button>
            <button className="secondaryActionButton compactAction" type="button" onClick={regenerateDraftDocument}><Download size={13} strokeWidth={2.4} aria-hidden="true" /> HWPX 다시 생성</button>
          </div>
          {reviewRequestGuide ? <p className="helperText">{reviewRequestGuide}</p> : null}
          {savedMessage ? <p className="successBanner"><span className="successBannerBadge"><CheckCircle2 size={12} strokeWidth={2.4} aria-hidden="true" />저장 완료</span>{savedMessage}</p> : null}
          {generatedFileMessage ? <p className="apiPendingMessage" role="status">{generatedFileMessage}</p> : null}
          {/* consultationId는 selectedCase.coreId보다 draftDocument.consultationId(방금 생성 응답이 실제로
              알려준 값)를 우선 씁니다. 사건을 core-api에 처음 동기화하면서 같은 함수 실행 중 초안까지
              만든 경우, selectedCase는 이 렌더의 클로저에 잡힌 값이라 아직 갱신 전이라 비어 있을 수
              있는데, draftDocument는 방금 성공한 생성 응답 자체라 항상 최신값입니다. */}
          <GeneratedFileBox document={draftDocument} consultationId={draftDocument?.consultationId || selectedCase?.coreId} />
        </section>
      </main>
    );
  }

  return (
    <main className="workspacePage">
      <section className="workflowPanel draftPanel">
        <WorkPageHeader
          title={isLawyerReviewer ? '서식 초안 검토' : '서식 초안 생성'}
          description={isLawyerReviewer
            ? '제출된 초안을 확인하고 승인 또는 반려하세요.'
            : '사건과 서식을 선택한 뒤 초안을 생성하세요.'}
        />
        <div className="apiPendingBanner">
          <FileText className="apiPendingBannerIcon" size={18} strokeWidth={2.2} aria-hidden="true" />
          <span className="apiPendingBannerText">
            <strong>{isLawyerReviewer ? 'HWPX 서식 검토 연동' : 'HWPX 서식 생성 연동'}</strong>
            <small>
              {isLawyerReviewer
                ? '초안 검토 · 결과 저장'
                : 'HWPX 생성 · 검토 요청 · 승인 흐름'}
            </small>
          </span>
        </div>
        <div className="inlineControls">
          <CasePicker consultations={consultations} value={caseId} onChange={setCaseId} />
        </div>
        {selectedCase ? (
          <div className="draftCaseSummary">
            <span><small>사건 유형</small><strong>{draftCaseType || '분석 전'}</strong></span>
            <span><small>상담 제목</small><strong>{selectedCase.title}</strong></span>
            <span><small>첨부자료</small><strong>{selectedCase.attachments?.length || 0}건</strong></span>
          </div>
        ) : null}
        {selectedCase ? (
          <section className="documentReviewPanel">
            <div className="panelTitleRow">
              <h3><ClipboardList size={16} strokeWidth={2.2} className="sectionIcon" aria-hidden="true" /> {isLawyerReviewer ? '제출된 서식 검토' : '제출한 서식 상태'}</h3>
              {documentsLoading ? <span className="helperText">불러오는 중…</span> : null}
            </div>
            {!selectedCase.coreId ? (
              <InlineEmptyNotice>로컬 상담 · 서식 검토 불러오기 불가</InlineEmptyNotice>
            ) : caseDocuments.length ? (
              <div className="documentReviewList">
                {caseDocuments.map((doc) => {
                  const lawyerEdit = readLawyerDraftEdit(doc.document_id);
                  const isReviewingThis = reviewingDocumentId === doc.document_id;
                  return (
                    <div className="documentReviewRow" key={doc.document_id}>
                      <div className="documentReviewInfo">
                        <strong><FileText size={14} strokeWidth={2.2} aria-hidden="true" /> {doc.form_name}</strong>
                        <span className={`statusChip tone-${documentStatusTone(doc.status)}`}>{DOCUMENT_STATUS_LABEL[doc.status] || doc.status}</span>
                        {lawyerEdit ? <span className="statusChip tone-warn">변호사 수정본</span> : null}
                        <GeneratedFileLink
                          path={doc.draft_file_path}
                          consultationId={selectedCase.coreId}
                          documentId={doc.document_id}
                          content={lawyerEdit?.content || doc.draft_content}
                          downloadFileName={doc.download_file_name}
                        />
                        {/* 서버에는 반영되지 않는 로컬 전용 수정본이라는 점을 항상 보이는 캡션으로
                            남겨, 상담원이 이걸 서버에 저장된 최종본으로 오해하지 않게 합니다. */}
                        {lawyerEdit ? <p className="localEditOnlyCaption">로컬 임시 저장 · 이 브라우저에서만 표시</p> : null}
                        {lawyerEdit && !isReviewingThis ? <pre className="documentLawyerEditPreview">{lawyerEdit.content}</pre> : null}
                        {doc.review_note ? <p className="reasonText">지난 검토 코멘트: {doc.review_note}</p> : null}
                        {doc.requested_materials?.length ? <p className="reasonText">요청 자료: {doc.requested_materials.join(', ')}</p> : null}
                      </div>
                      {isLawyerReviewer && doc.status === 'SUBMITTED_FOR_REVIEW' ? (
                        isReviewingThis ? (
                          <div className="documentReviewForm">
                            <div className="draftView">
                              <div className="draftViewPane">
                                <div className="draftViewPaneHeader"><strong>편집</strong></div>
                                <textarea
                                  className="documentReviewContentEditor"
                                  value={reviewContentDraft}
                                  onChange={(event) => setReviewContentDraft(event.target.value)}
                                  placeholder="서식 초안 내용을 입력하거나 고치세요."
                                />
                              </div>
                              <div className="draftViewPane">
                                <div className="draftViewPaneHeader">
                                  <strong>미리보기</strong>
                                  <span className="statusChip tone-info">변호사 수정본</span>
                                </div>
                                {reviewContentDraft ? <pre>{reviewContentDraft}</pre> : <p className="helperText">입력 내용 없음</p>}
                              </div>
                            </div>
                            <textarea
                              value={reviewNoteText}
                              onChange={(event) => setReviewNoteText(event.target.value)}
                              placeholder="내부 검토 메모 (선택)"
                            />
                            <div className="inlineControls">
                              <button type="button" onClick={cancelDocumentReview} disabled={reviewPending}>취소</button>
                              <button
                                className="primaryButton"
                                type="button"
                                onClick={() => confirmDocumentReview(doc)}
                                disabled={reviewPending}
                              >
                                {reviewPending ? '처리하는 중…' : '검토 완료'}
                              </button>
                            </div>
                          </div>
                        ) : (
                          // 실제 승인 확정 버튼(3001-3008줄)과 같은 '검토 완료' 문구를 여기 편집 시작
                          // 버튼에도 쓰면 눌러도 아무 것도 끝나지 않아 헷갈립니다(코치 피드백).
                          <div className="inlineControls">
                            <button className="secondaryActionButton" type="button" onClick={() => startDocumentReview(doc)}>검토하기</button>
                          </div>
                        )
                      ) : null}
                    </div>
                  );
                })}
              </div>
            ) : (
              !documentsLoading ? <InlineEmptyNotice>제출된 서식 초안 없음</InlineEmptyNotice> : null
            )}
          </section>
        ) : null}
        {!isLawyerReviewer ? (
          /* 시안: '서식 선택'과 '추출 필드 자동 채움', 그리고 생성 버튼까지 흰 카드 하나에 담깁니다. */
          <div className="draftSelectCard">
            <div className="workflowColumns">
              <div>
                <h3><FileText size={16} strokeWidth={2.2} className="sectionIcon" aria-hidden="true" /> 서식 선택</h3>
                {/* 0단계: 이 사건 분류에 맞는 서식만 보기.
                    291개에서 손으로 좁히지 않아도 되게, 확정된 소분류로 한 번에 걸러줍니다. */}
                <div className="templateScopeRow">
                  <button
                    className={scopeToCase ? 'templateScopeToggle active' : 'templateScopeToggle'}
                    type="button"
                    aria-pressed={scopeToCase}
                    disabled={!draftCaseType}
                    onClick={() => { setOnlyForCase((current) => !current); setMajorFilter('전체'); setMinorFilter('전체'); }}
                  >
                    {draftCaseType ? `'${draftCaseType}' 서식만 보기` : '사건을 먼저 선택하세요'}
                  </button>
                  {scopeToCase && !filteredTemplates.length ? (
                    <span className="templateScopeEmpty">연결 서식 없음 · 전체 검색</span>
                  ) : null}
                </div>
                {/* 1단계: 대분류 탭 (4개 + 전체) — 소분류 29개를 한꺼번에 늘어놓지 않고 단계적으로 좁힙니다. */}
                <div className="categoryTabs">
                  {['전체', ...caseCategories.map((category) => category.key)].map((category) => (
                    <button
                      className={majorFilter === category ? 'categoryTab active' : 'categoryTab'}
                      type="button"
                      key={category}
                      onClick={() => { setMajorFilter(category); setMinorFilter('전체'); }}
                    >
                      {category}
                    </button>
                  ))}
                </div>
                {/* 2단계: 소분류 드롭다운 + 서식명 검색 */}
                <div className="templateFilterRow">
                  <div className="templateFilterPicker">
                    <ChoicePicker
                      value={minorFilter}
                      options={minorOptions.map((option, index) => ({
                        value: option,
                        label: index === 0 ? '소분류 전체' : option,
                      }))}
                      onChange={setMinorFilter}
                      disabled={!activeMajor}
                      placeholder="소분류 선택"
                    />
                  </div>
                  <input
                    className="templateSearchInput"
                    value={searchText}
                    onChange={(event) => setSearchText(event.target.value)}
                    placeholder="서식명 검색"
                  />
                </div>
                <p className="templateCount">
                  검색 결과 {templates.length}건
                  {recommendLoading ? <span className="templateRecommendLoading"> · AI 추천 확인 중…</span> : null}
                </p>
                {/* 3단계: 서식 목록 */}
                <div className="templateList">
                  {templates.length ? templates.map((item) => {
                    const aiMatch = aiRecommendations.find((rec) => rec.form_name === item.templateName);
                    return (
                      <button
                        className={selectedTemplate?.templateName === item.templateName ? 'templateRow active' : 'templateRow'}
                        type="button"
                        key={item.templateName}
                        onClick={() => setTemplate(item.templateName)}
                      >
                        <span className="templateRowText">
                          <span className="templateRowName">
                            {item.templateName}
                            {aiMatch ? <em className="templateAiBadge" title={aiMatch.reason || 'AI 추천 서식'}><Sparkles size={10} strokeWidth={2.4} aria-hidden="true" />AI 추천</em> : null}
                          </span>
                          <span className="templateRowMeta">{item.caseCategory} · {item.caseType}</span>
                        </span>
                        <span
                          className={favorites.includes(item.templateName) ? 'favoriteToggle active' : 'favoriteToggle'}
                          role="button"
                          tabIndex={0}
                          aria-label={favorites.includes(item.templateName) ? '즐겨찾기 해제' : '즐겨찾기 추가'}
                          onClick={(event) => handleToggleFavorite(item.templateName, event)}
                        >
                          {favorites.includes(item.templateName)
                            ? <Star size={13} strokeWidth={2.2} fill="currentColor" aria-hidden="true" />
                            : <Plus size={13} strokeWidth={2.4} aria-hidden="true" />}
                        </span>
                      </button>
                    );
                  }) : <InlineEmptyNotice>조건에 맞는 서식이 없습니다.</InlineEmptyNotice>}
                </div>
              </div>
              <div>
                <h3><ListChecks size={16} strokeWidth={2.2} className="sectionIcon" aria-hidden="true" /> 추출 필드 자동 채움</h3>
                <div className="draftApiPlan">
                  <strong>자동 채움에 쓰이는 정보</strong>
                  <span>서식명, 상담 번호, 분석 요약, 누락 필드, 첨부자료 정보</span>
                </div>
                <div className="scrollBox">
                  {selectedTemplate ? (
                    <div className="draftFieldList">
                      {draftFields.map((item) => {
                        // '당사자 정보'·'청구 취지'처럼 짧은 값은 라벨과 한 줄에 나란히 둬도 읽기 좋지만,
                        // '관련 사실관계'처럼 문장 전체가 들어가는 값은 같은 방식으로 좁게 우측 정렬하면
                        // 라벨·값이 둘 다 세로로 쪼개져 읽기 힘들어집니다. 값 길이에 따라 레이아웃을 바꿉니다.
                        const isLongValue = item.filled && item.value.length > 18;
                        return (
                          <div key={item.field} className={`draftFieldRow ${item.filled ? 'filled' : 'missing'}${isLongValue ? ' longValue' : ''}`}>
                            <span className="draftFieldName">{item.field}</span>
                            <span className="draftFieldValue">{item.filled ? item.value : '누락 - 확인 필요'}</span>
                          </div>
                        );
                      })}
                    </div>
                  ) : <p>서식을 선택하면 항목 표시</p>}
                </div>
              </div>
            </div>
            <div className="draftFinalActions">
              <button className="primaryButton compactAction" type="button" onClick={goToPreview} disabled={!selectedTemplate}>서식 초안 생성</button>
            </div>
          </div>
        ) : null}
      </section>
    </main>
  );
}

function SearchWorkbench({ consultations }) {
  const [caseId, setCaseId] = useState(caseOptions(consultations)[0].id);
  const [referenceType, setReferenceType] = useState('precedent');
  const [mode, setMode] = useState('추천');
  const [query, setQuery] = useState('');
  const [searched, setSearched] = useState(false);
  const [selected, setSelected] = useState([]);
  const [referenceMessage, setReferenceMessage] = useState('');
  const label = referenceType === 'precedent' ? '판례' : referenceType === 'similar' ? '유사 상담사례' : '법령';
  const selectedCase = consultations.find((item) => String(item.id) === String(caseId));
  const results = searched || mode === '추천' ? searchReferenceCandidates({ type: referenceType, query, caseType: selectedCase?.analysis?.caseType || selectedCase?.type }) : [];
  const selectedTitles = selected.map((item) => item.title);
  const runAiReferenceSearch = () => {
    setSearched(true);
    setReferenceMessage('추천 후보 표시 · API 연동 전 임시 목록');
  };
  const adoptReference = (item) => {
    setSelected((current) => current.some((value) => value.id === item.id) ? current : [...current, item]);
  };

  return (
    <main className="workspacePage">
      <section className="workflowPanel searchPanel">
        {/* 세 번째 탭 '유사 상담사례'는 법령·판례가 아닌데도 제목·설명이 법령·판례만
            가리켜, 이 탭이 여기 왜 있는지 헷갈릴 수 있습니다(코치 피드백). 설명 문구에
            유사 사례도 포함되어 있음을 밝힙니다. */}
        <WorkPageHeader
          title="법령·판례"
          description="사건에 맞는 법령·판례와 유사 상담사례를 찾아 검토 자료에 반영하세요."
        />
        <div className="inlineControls">
          <CasePicker
            consultations={consultations}
            value={caseId}
            onChange={(nextCaseId) => {
              setCaseId(nextCaseId);
              setSelected([]);
              setReferenceMessage('');
            }}
          />
        </div>
        {selectedCase ? (
          <div className="referenceCaseSummary">
            <span><small>사건 유형</small><strong>{selectedCase.analysis?.caseType || selectedCase.type || '미분류'}</strong></span>
            <span><small>긴급도</small><strong>{selectedCase.analysis?.urgency || '미확인'}</strong></span>
            <span><small>구조대상</small><strong>{selectedCase.analysis?.eligibility || '검토 필요'}</strong></span>
          </div>
        ) : null}
        {/* 시안: 자료 종류(판례/법령/유사 상담사례)는 왼쪽, 추천/직접 검색 전환은 같은 줄 오른쪽. */}
        <div className="referenceToolbar">
          <div className="segmented referenceTypeTabs">
            {[
              { key: 'precedent', label: '판례' },
              { key: 'statute', label: '법령' },
              { key: 'similar', label: '유사 상담사례' },
            ].map((item) => (
              <button
                className={referenceType === item.key ? 'active' : ''}
                type="button"
                key={item.key}
                onClick={() => {
                  setReferenceType(item.key);
                  setSelected([]);
                  setSearched(mode === '추천');
                }}
              >
                {item.label}
              </button>
            ))}
          </div>
          <div className="segmented referenceModeTabs">
            {['추천', '직접 검색'].map((item) => <button className={mode === item ? 'active' : ''} type="button" key={item} onClick={() => { setMode(item); setSearched(item === '추천'); }}>{item}</button>)}
          </div>
        </div>
        {mode === '직접 검색' ? (
          <div className="referenceSearchBox">
            <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder={`${label} 검색어`} />
            <button type="button" onClick={() => setSearched(true)}>검색</button>
          </div>
        ) : null}
        <div className="referenceActionBar">
          <div>
            <strong>{mode === '추천' ? '상담 분석 기반 추천' : '직접 검색 결과 검토'}</strong>
            <span>{selected.length ? `${selected.length}개 선택됨` : '검토에 쓸 후보 선택'}</span>
          </div>
          <div className="referenceActionButtons">
            {/* '추천' 모드에서는 사건을 고르는 순간 results가 이미 자동으로 채워져 있어
                (위 results 계산 참고), 이 버튼을 눌러도 화면이 바뀌지 않는 빈 동작이었습니다
                (코치 피드백). 직접 검색 모드에서만 다시 불러오는 의미가 있으므로 그때만 보여줍니다. */}
            {mode === '직접 검색' ? (
              <button className="secondaryActionButton compactAction" type="button" onClick={runAiReferenceSearch}>AI 추천 실행</button>
            ) : null}
            <button
              className="primaryButton compactAction"
              type="button"
              // '반영 완료'라고 말했지만 실제로는 저장 없이 이 화면 상태에만 남아, 화면을
              // 나가면 선택이 사라졌습니다(코치 피드백). 저장하지 않는다는 사실을 문구로
              // 정확히 알립니다.
              onClick={() => setReferenceMessage('이 화면에 임시로 담아뒀어요 · 서식 작성 화면으로 이동하면 사라져요')}
              disabled={!selected.length}
            >
              선택 항목 담기
            </button>
          </div>
        </div>
        {referenceMessage ? <p className="apiPendingMessage" role="status">{referenceMessage}</p> : null}
        <div className="workflowColumns">
          <div>
            <h3><BookOpen size={16} strokeWidth={2.2} className="sectionIcon" aria-hidden="true" /> {label} 목록</h3>
            <div className="referenceList">
              {results.length ? results.map((item) => {
                const isSelected = selectedTitles.includes(item.title);
                return (
                  <button className={isSelected ? 'referenceCard selected' : 'referenceCard'} type="button" key={item.id} onClick={() => adoptReference(item)}>
                    <span className="referenceCardTitle"><Gavel size={13} strokeWidth={2.2} aria-hidden="true" /> {item.title}</span>
                    <span className="referenceCardMeta">{item.source} · {item.caseType}</span>
                    <strong className={`statusChip ${isSelected ? 'tone-success' : 'tone-muted'}`}>
                      {isSelected ? <CheckCircle2 size={12} strokeWidth={2.4} aria-hidden="true" /> : null} {isSelected ? '선택됨' : '선택'}
                    </strong>
                  </button>
                );
              }) : <InlineEmptyNotice>조건 일치 {label} 없음</InlineEmptyNotice>}
            </div>
          </div>
          <div>
            <h3><ClipboardList size={16} strokeWidth={2.2} className="sectionIcon" aria-hidden="true" /> 검토에 반영할 자료</h3>
            <div className="referenceSelectedPanel">
              {selected.length ? selected.map((item) => (
                <button type="button" key={item.id} onClick={() => setSelected(selected.filter((value) => value.id !== item.id))}>
                  <span>{item.title}</span>
                  <small>{item.source}</small>
                  <strong>빼기</strong>
                </button>
              )) : <p>선택된 자료가 없습니다.</p>}
            </div>
          </div>
        </div>
      </section>
    </main>
  );
}

function NotificationPanel({ role, currentUser, notifications = [], onReadNotifications, onDeleteNotification, onOpenNotification }) {
  const confirm = useConfirm();
  const notificationKey = `${role}:${currentUser?.email || 'all'}`;
  const roleNotifications = notifications.filter((item) => {
    if (!item.roles?.includes(role)) return false;
    if (item.recipientEmail && item.recipientEmail !== currentUser?.email) return false;
    return !item.deletedBy?.includes(role) && !item.deletedBy?.includes(notificationKey);
  });
  const unreadCount = roleNotifications.filter((item) => !item.readBy?.includes(role) && !item.readBy?.includes(notificationKey)).length;
  const handleDelete = async (event, item, unread) => {
    event.stopPropagation();
    if (unread) {
      const accepted = await confirm({
        title: '읽지 않은 알림을 삭제할까요?',
        message: `「${item.title}」\n읽지 않은 알림이 삭제됩니다.`,
        confirmLabel: '삭제',
        tone: 'danger',
      });
      if (!accepted) return;
    }
    onDeleteNotification?.(item.id, role, currentUser?.email);
  };
  return (
    <section className="workPanel notificationPanel">
      <WorkPageHeader
        title="알림"
        description="새 알림을 확인하고 해당 업무로 바로 이동하세요."
        meta={(
          <span className="notificationHeaderMeta">
            <span className="notificationCount">새 알림 {unreadCount}건</span>
            {/* 알림이 쌓일수록 이 버튼을 찾아 목록 맨 아래까지 내려야 했던 문제를 없애기 위해
                목록 위(헤더 옆)로 옮겼습니다. */}
            <button className="ghostActionButton compactAction" type="button" onClick={() => onReadNotifications?.(role, currentUser?.email)} disabled={!unreadCount}><BellOff size={13} strokeWidth={2.4} aria-hidden="true" /> 전체 읽음 처리</button>
          </span>
        )}
      />
      <div className="utilityContentCard notificationContentCard">
        {roleNotifications.length ? (
          <div className="notificationList">
            {roleNotifications.map((item) => {
              const unread = !item.readBy?.includes(role) && !item.readBy?.includes(notificationKey);
              return (
                <article
                  className={unread ? 'notificationItem unread' : 'notificationItem read'}
                  key={item.id}
                  role="button"
                  tabIndex={0}
                  onClick={() => onOpenNotification?.(item)}
                  onKeyDown={(event) => {
                    if (event.key === 'Enter' || event.key === ' ') onOpenNotification?.(item);
                  }}
                >
                  <div className="notificationItemTop">
                    <strong className="notificationItemTitle">
                      <i className="notificationDot" aria-hidden="true" />
                      {unread ? <Bell size={13} strokeWidth={2.4} aria-hidden="true" /> : <BellOff size={13} strokeWidth={2.2} aria-hidden="true" />}
                      {item.title}
                    </strong>
                    <span className="notificationItemTime">{formatDateTimeLabel(item.createdAt)}</span>
                  </div>
                  <p className="notificationItemMessage">{item.message}</p>
                  <div className="notificationActions">
                    <span className="notificationState">{unread ? '바로 처리 ›' : '내용 보기'}</span>
                    <button className="notificationDelete" type="button" onClick={(event) => handleDelete(event, item, unread)}><Trash2 size={12} strokeWidth={2.4} aria-hidden="true" /> 삭제</button>
                  </div>
                </article>
              );
            })}
          </div>
        ) : (
          <div className="notificationEmptyState" role="status">
            <InlineEmptyNotice>새 알림이 없습니다.</InlineEmptyNotice>
            <p>새로운 업무 알림이 도착하면 이곳에서 확인할 수 있습니다.</p>
          </div>
        )}
      </div>
    </section>
  );
}

function ProfilePanel({ role, currentUser, onUpdateProfile }) {
  const [form, setForm] = useState({
    email: currentUser?.email || '',
    organization: currentUser?.organization || '',
    phone: currentUser?.phone || '',
    currentPassword: '',
    password: '',
    confirmPassword: '',
  });
  const [message, setMessage] = useState('');
  const [saving, setSaving] = useState(false);
  const mismatch = form.confirmPassword && form.password !== form.confirmPassword;
  const roleLabel = role === 'counselor' ? '상담원' : role === 'lawyer' ? '변호사' : '관리자';
  // 상담원/변호사는 가입 시 등록된 이메일·소속기관이 계정 식별/조직 배정 기준이라
  // 본인이 임의로 바꾸지 못하도록 막습니다. (변경이 필요하면 관리자에게 문의)
  const lockContactFields = role === 'counselor' || role === 'lawyer';
  // 소속은 '지부 / 부서' 한 문자열로 저장되어 있어, 화면에서는 두 칸으로 나눠 보여줍니다.
  // 부서 없이 가입한 예전 계정도 있으므로 branch 필드를 우선 쓰고 없으면 앞부분을 사용합니다.
  const [savedBranch, ...savedDepartmentParts] = (currentUser?.organization || '').split(' / ');
  const branchValue = currentUser?.branch || savedBranch || '';
  const departmentValue = currentUser?.department || savedDepartmentParts.join(' / ');

  const save = async () => {
    if (!form.email) {
      setMessage('이메일을 입력해주세요.');
      return;
    }
    // 관리자만 이메일을 직접 고칠 수 있는데(상담원·변호사는 잠긴 필드), 회원가입 화면의
    // emailInvalid 검사가 여기엔 없어서 '@' 없는 값도 그대로 저장되던 문제가 있었습니다.
    if (!lockContactFields && !form.email.includes('@')) {
      setMessage('올바른 이메일 형식이 아닙니다.');
      return;
    }
    if (mismatch) {
      setMessage('비밀번호와 비밀번호 확인이 일치하지 않습니다.');
      return;
    }
    // 비밀번호는 core-api로 따로 보냅니다.
    //
    // 예전에는 이 값을 onUpdateProfile에 함께 넘겼는데, 받는 쪽(App.updateProfile)이
    // 실제로는 저장하지 않으면서 감사 로그에는 '비밀번호 변경'으로 남겼습니다. 그래서
    // 어떤 값을 넣어도 바뀌지 않는데 화면에는 저장됐다고 뜨는 상태였습니다.
    const wantsPasswordChange = Boolean(form.password);
    if (wantsPasswordChange && !form.currentPassword) {
      setMessage('비밀번호를 바꾸려면 현재 비밀번호를 입력해주세요.');
      return;
    }

    const effectiveEmail = lockContactFields ? (currentUser?.email || '') : form.email;
    // 가입 화면과 동일한 비밀번호 규칙을 프로필 변경에도 적용합니다.
    if (wantsPasswordChange) {
      const passwordRuleError = validatePassword(form.password, effectiveEmail);
      if (passwordRuleError) {
        setMessage(passwordRuleError);
        return;
      }
    }

    setSaving(true);
    try {
      if (wantsPasswordChange) {
        // 서버가 현재 비밀번호 확인·동일 비밀번호 차단·작성규칙 검사를 모두 담당합니다.
        // 실패하면 여기서 멈춰, 연락처만 저장되고 비밀번호는 안 바뀐 채 성공 메시지가
        // 뜨는 일이 없게 합니다.
        await changeCorePassword({ currentPassword: form.currentPassword, newPassword: form.password });
      }
      onUpdateProfile({
        // 잠긴 필드는 화면에서 수정이 막혀 있지만, 혹시 모를 우회를 방지하고자 저장 시에도
        // 원래 계정 값(currentUser)을 그대로 사용하고 form 값은 무시합니다.
        email: lockContactFields ? (currentUser?.email || '') : form.email,
        organization: lockContactFields ? (currentUser?.organization || '') : form.organization,
        // 연락처는 신원·소속 확인용 정보가 아니라 실무 연락 목적이라 역할과 무관하게 본인이 직접 수정할 수 있습니다.
        phone: form.phone,
        passwordChanged: wantsPasswordChange,
      });
      setMessage(wantsPasswordChange ? '프로필과 비밀번호가 저장되었습니다.' : '프로필이 저장되었습니다.');
      setForm((current) => ({ ...current, currentPassword: '', password: '', confirmPassword: '' }));
    } catch (error) {
      setMessage(error.message || '비밀번호를 변경하지 못했습니다.');
    } finally {
      setSaving(false);
    }
  };

  return (
    <section className="workPanel profilePanel">
      <WorkPageHeader
        title="내 정보"
        description={`${roleLabel} 계정의 연락처와 비밀번호를 관리하세요.`}
      />
      <div className="utilityContentCard profileContentCard">
      <div className="profileFormCard">
      <label className="field">
        <span><span className="fieldLabelWithIcon"><User size={14} strokeWidth={2.4} aria-hidden="true" /> 이메일</span></span>
        <input value={form.email} onChange={(event) => setForm({ ...form, email: event.target.value })} type="email" placeholder="이메일 입력" readOnly={lockContactFields} disabled={lockContactFields} />
      </label>
      {/* 상담원·변호사는 가입 시 고른 지부와 입력한 부서를 각각 보여줍니다.
        * 둘 다 조직 배정 기준이라 이메일과 마찬가지로 본인이 고칠 수 없습니다. */}
      {lockContactFields ? (
        <div className="formGrid">
          <label className="field">
            <span>소속기관 (지부)</span>
            <input value={branchValue} placeholder="가입 시 선택한 소속 지부" readOnly disabled />
          </label>
          <label className="field">
            <span>부서</span>
            <input value={departmentValue} placeholder="가입 시 입력한 부서" readOnly disabled />
          </label>
        </div>
      ) : (
        <label className="field">
          <span>소속지부 / 부서</span>
          <input value={form.organization} onChange={(event) => setForm({ ...form, organization: event.target.value })} placeholder="대한법률구조공단 / 전산" />
        </label>
      )}
      {lockContactFields ? <p className="helperText">이메일·소속은 관리자에게 변경 요청</p> : null}
      <label className="field">
        <span>연락처</span>
        <input value={form.phone} onChange={(event) => setForm({ ...form, phone: event.target.value })} type="tel" placeholder="010-0000-0000" />
      </label>
      <div className="formGrid">
        <label className="field">
          <span><span className="fieldLabelWithIcon"><Lock size={14} strokeWidth={2.4} aria-hidden="true" /> 현재 비밀번호</span></span>
          <input value={form.currentPassword} onChange={(event) => setForm({ ...form, currentPassword: event.target.value })} type="password" placeholder="비밀번호를 바꿀 때만 입력" autoComplete="current-password" />
        </label>
      </div>
      <div className="formGrid">
        <label className="field">
          <span><span className="fieldLabelWithIcon"><Lock size={14} strokeWidth={2.4} aria-hidden="true" /> 새 비밀번호</span></span>
          <input value={form.password} onChange={(event) => setForm({ ...form, password: event.target.value })} type="password" placeholder="변경할 때만 입력" autoComplete="new-password" />
        </label>
        <label className="field">
          <span><span className="fieldLabelWithIcon"><Lock size={14} strokeWidth={2.4} aria-hidden="true" /> 새 비밀번호 확인</span></span>
          <input value={form.confirmPassword} onChange={(event) => setForm({ ...form, confirmPassword: event.target.value })} type="password" placeholder="비밀번호 확인" />
        </label>
      </div>
      <p className="helperText">{PASSWORD_RULE_TEXT}</p>
      {mismatch ? <p className="formError">비밀번호와 비밀번호 확인이 일치하지 않습니다.</p> : null}
      {message ? <p className={message.includes('저장') ? 'helperText success' : 'formError'}>{message}</p> : null}
      <button className="primaryButton" type="button" onClick={save} disabled={saving}>{saving ? '저장 중...' : '프로필 수정 저장'}</button>
      </div>
      </div>
    </section>
  );
}

function UtilityPanel({ view, role, consultations, onCreateConsultation, onRequestLegalReview, onAnalysisSaved, onUpdateConsultation, currentUser, onUpdateProfile, notifications, onReadNotifications, onDeleteNotification, onOpenNotification, onGoToDashboard, onNotify, focusedConsultationId, focusedTemplateName, onOpenAnalysis, onOpenDraft, analysisRuns, onStartAnalysis }) {
  // '상담 등록'은 상담원 고유 업무입니다. 다른 역할에서 실수로 activeView가 넘어와도
  // 접수 화면이 열리지 않도록 역할을 한 번 더 확인합니다. (네비게이션 메뉴 구성과 이중 방어)
  if (view === '상담 등록') return role === 'counselor' ? (
    <UploadWorkbench
      consultations={consultations}
      onCreateConsultation={onCreateConsultation}
      onUpdateConsultation={onUpdateConsultation}
      onGoToRealtimeAnalysis={() => onOpenAnalysis?.()}
    />
  ) : <ProfilePanel role={role} currentUser={currentUser} onUpdateProfile={onUpdateProfile} />;
  // 법령·판례 검색은 변호사 전용입니다. 메뉴에서 이미 뺐지만, 상담원 role로 이 화면에
  // 들어오는 경로가 남아있을 수 있어 한 번 더 막습니다. (상담 등록과 같은 이중 방어 규칙)
  if (view === '법률, 판례') return role === 'lawyer' ? <SearchWorkbench consultations={consultations} /> : <ProfilePanel role={role} currentUser={currentUser} onUpdateProfile={onUpdateProfile} />;
  if (view === '서식 생성') return (
    <DraftWorkbench
      consultations={consultations}
      currentUser={currentUser}
      role={role}
      onUpdateConsultation={onUpdateConsultation}
      onNotify={onNotify}
      focusedConsultationId={focusedConsultationId}
      focusedTemplateName={focusedTemplateName}
    />
  );
  if (view === '알림') return <NotificationPanel role={role} currentUser={currentUser} notifications={notifications} onReadNotifications={onReadNotifications} onDeleteNotification={onDeleteNotification} onOpenNotification={onOpenNotification} />;
  if (view === '기타' && role === 'lawyer') return <ProfilePanel role={role} currentUser={currentUser} onUpdateProfile={onUpdateProfile} />;
  if (view === '기타') return <AnalysisWorkbench consultations={consultations} onCreateConsultation={onCreateConsultation} onUpdateConsultation={onUpdateConsultation} onRequestLegalReview={onRequestLegalReview} onAnalysisSaved={onAnalysisSaved} currentUser={currentUser} onGoToDashboard={onGoToDashboard} onOpenDraft={onOpenDraft} focusedConsultationId={focusedConsultationId} analysisRuns={analysisRuns} onStartAnalysis={onStartAnalysis} />;
  return <ProfilePanel role={role} currentUser={currentUser} onUpdateProfile={onUpdateProfile} />;
}

// ── 아래는 dashboards.jsx(변호사 대시보드의 서식 초안 검토 대기 패널·HITL 모달)가 그대로 가져다 쓰는
// 표시 전용 헬퍼입니다. DraftWorkbench 내부 로직과는 독립적이라, 이 파일의 다른 부분과 상관없이
// 안전하게 export만 유지합니다. ──

// /consult/analyze가 돌려준 구조검토 체크리스트입니다.
// 승소·집행·타당성은 결론이 아니라 '신호'이므로, 판정처럼 보이지 않게 근거 문장 그대로만 둡니다.
function ReliefReviewSummary({ review }) {
  const signals = [
    { label: '승소 가능성', signal: review.winnability },
    { label: '집행 가능성', signal: review.executability },
    { label: '구조 타당성', signal: review.appropriateness },
  ].filter((item) => item.signal?.note);
  return (
    <div className="reliefReviewBox">
      <p className="reliefReviewHead">
        <span className="statusChip tone-info">증빙 {review.evidenceStatusLabel}</span>
        {review.matchedReasons.length ? <span className="reliefReviewReasons">{review.matchedReasons.join(' · ')}</span> : null}
      </p>
      {review.judgmentNote ? <p className="reasonText">판정 근거: {review.judgmentNote}</p> : null}
      {signals.length ? (
        <dl className="reliefSignalList">
          {signals.map((item) => (
            <div key={item.label}>
              <dt>{item.label}</dt>
              <dd>{item.signal.note}</dd>
            </div>
          ))}
        </dl>
      ) : null}
      {review.lawyerSummary ? <p className="reliefLawyerSummary">변호사 검토 요약: {review.lawyerSummary}</p> : null}
    </div>
  );
}

// checklist_summary_for_lawyer는 "[구조대상자 여부] 대상 (...)\n[승소가능성] ...\n※ 위 내용은..."
// 형태의 한 덩어리 문자열입니다. 항목별 대괄호 태그가 그대로 화면에 보이면 읽기 어려우므로,
// 줄 단위로 "[라벨] 내용" 패턴을 잘라 label/value 목록으로 만들고, 맨 끝 "※..." 안내문은 따로
// 분리해 각주로 둡니다. 값이 빈 항목(해당 신호에 review_note가 없던 경우)은 목록에서 뺍니다.
function parseLawyerSummary(rawText = '') {
  const footnoteIndex = rawText.indexOf('※');
  const bodyText = footnoteIndex >= 0 ? rawText.slice(0, footnoteIndex) : rawText;
  const footnote = footnoteIndex >= 0 ? rawText.slice(footnoteIndex).trim() : '';
  const items = bodyText
    .split('\n')
    .map((line) => {
      const match = line.match(/^\[([^\]]+)\]\s*(.*)$/);
      if (!match) return null;
      const value = match[2].trim();
      return value ? { label: match[1].trim(), value } : null;
    })
    .filter(Boolean);
  return { items, footnote };
}

// requires_lawyer_review + checklist_summary_for_lawyer 전용 카드입니다. ReliefReviewDetailTabs(4탭)의
// 근거 상세와는 성격이 달라 별도 카드로 분리합니다 — 이쪽은 변호사에게 바로 넘길 수 있는 한 줄 요약이고,
// 탭 쪽은 상담원이 각 신호의 근거를 하나씩 파고들 때 보는 상세 화면입니다.
function ReliefLawyerSummaryCard({ detail }) {
  if (!detail) return null;
  const { items, footnote } = parseLawyerSummary(detail.lawyerSummary || '');
  if (!detail.requiresLawyerReview && !items.length && !footnote) return null;
  return (
    <>
      {detail.requiresLawyerReview ? (
        <div className="hitlBanner">
          <Info className="hitlBannerIcon" size={16} strokeWidth={2.4} aria-hidden="true" />
          <span><strong>변호사 최종 검토 필요</strong></span>
        </div>
      ) : null}
      {items.length ? (
        <dl className="reliefLawyerSummaryList">
          {items.map((item) => (
            <div key={item.label}>
              <dt>{item.label}</dt>
              <dd>{item.value}</dd>
            </div>
          ))}
        </dl>
      ) : null}
      {footnote ? <p className="reliefLawyerSummary">{footnote}</p> : null}
    </>
  );
}

// 체크박스 5항목(법률구조 대상 여부/증빙/승소가능성/집행가능성/구조타당성) 옆에 AI 근거를 한 줄
// 덧붙입니다. 체크 여부(checked)는 절대 건드리지 않습니다 — 상담원이 직접 확인하고 체크하는
// 항목이라는 HITL 원칙은 그대로이고, 이건 표시 전용 참고 문구입니다. requestEligibilityCandidate
// 등 기존 코드가 이미 쓰는 item.label.includes(...) 매칭 방식을 그대로 따릅니다.
function checklistItemNote(item, detail) {
  if (!detail) return null;
  if (item.label.includes('대상자 증빙서류')) {
    const evidence = detail.eligibility;
    if (!evidence) return null;
    const requiredEvidence = evidence.requiredEvidence.join(', ');
    const statusText = evidence.evidenceStatus === '충족' ? '제출 확인됨'
      : evidence.evidenceStatus === '미비' ? '미제출' : '확인불가';
    return requiredEvidence ? `${requiredEvidence} ${statusText}` : null;
  }
  if (item.label.includes('대상 여부')) return detail.eligibility?.judgmentNote || null;
  if (item.label.includes('승소 가능성')) return detail.winnability?.reviewNote || null;
  if (item.label.includes('집행 가능성')) return detail.executability?.reviewNote || null;
  if (item.label.includes('구조 타당성')) return detail.appropriateness?.reviewNote || null;
  return null;
}

// 위험 신호는 노트 문장에 묻히면 놓치기 쉬워 별도 칩으로 뺍니다 — ReliefReviewDetailTabs의 탭 점
// (categoryTabDot)과 같은 두 조건을 그대로 씁니다.
function checklistItemFlag(item, detail) {
  if (!detail) return null;
  if (item.label.includes('승소 가능성') && detail.winnability?.statuteOfLimitationsFlag === '계산 불가') {
    return { text: '소멸시효 계산 불가', tone: 'tone-warn' };
  }
  if (item.label.includes('구조 타당성') && (detail.appropriateness?.personalMotiveFlags || []).length) {
    return { text: detail.appropriateness.personalMotiveFlags.join(', '), tone: 'tone-danger' };
  }
  return null;
}

// null을 함부로 '미충족'/'언급 없음'으로 해석하지 않기 위한 3단계 라벨. income_criterion_met 같은
// 필드는 true/false/null(=아직 판단 불가) 셋을 구분해서 받는데, null을 false 취급하면 실제로는
// 판단이 안 된 사건을 '탈락'으로 잘못 보여주게 됩니다.
function criterionLabel(value) {
  if (value === true) return '충족';
  if (value === false) return '미충족';
  return '판단 보류';
}

function mentionLabel(value) {
  if (value === true) return '언급됨';
  if (value === false) return '언급 없음';
  return '미확인';
}

function evidenceStatusTone(status) {
  if (status === '충족') return 'tone-success';
  if (status === '미비') return 'tone-warn';
  return 'tone-muted';
}

function ReliefEligibilityTab({ data }) {
  if (!data) return <InlineEmptyNotice>표시할 정보 없음</InlineEmptyNotice>;
  return (
    <div className="reliefReviewBox">
      <p className="reliefReviewHead">
        <ShieldCheck size={14} strokeWidth={2.2} className="sectionIcon" aria-hidden="true" />
        <span className={`statusChip ${evidenceStatusTone(data.evidenceStatus)}`}>증빙 {data.evidenceStatus || '미확인'}</span>
      </p>
      <dl className="reliefSignalList">
        <div><dt>소득 기준</dt><dd>{criterionLabel(data.incomeCriterionMet)}</dd></div>
        <div><dt>신분 기준</dt><dd>{criterionLabel(data.statusCriterionMet)}</dd></div>
        {data.matchedReasons.length ? <div><dt>해당 사유</dt><dd>{data.matchedReasons.join(' · ')}</dd></div> : null}
        {data.requiredEvidence.length ? <div><dt>필요 증빙</dt><dd>{data.requiredEvidence.join(', ')}</dd></div> : null}
      </dl>
      {data.judgmentNote ? <p className="reasonText">판정 근거: {data.judgmentNote}</p> : null}
    </div>
  );
}

function ReliefWinnabilityTab({ data }) {
  if (!data) return <InlineEmptyNotice>표시할 정보 없음</InlineEmptyNotice>;
  const limitation = data.limitationStartDate
    ? `${data.limitationStartDate}${data.limitationPeriodYears != null ? ` (${data.limitationPeriodYears}년)` : ''}`
    : '';
  return (
    <div className="reliefReviewBox">
      <p className="reliefReviewHead">
        <TrendingUp size={14} strokeWidth={2.2} className="sectionIcon" aria-hidden="true" />
        <span className="statusChip tone-info">신뢰도 {data.extractionConfidence || '불명확'}</span>
        {data.statuteOfLimitationsFlag ? (
          <span className={`statusChip ${data.statuteOfLimitationsFlag === '계산 불가' ? 'tone-warn' : 'tone-info'}`}>소멸시효 {data.statuteOfLimitationsFlag}</span>
        ) : null}
      </p>
      <dl className="reliefSignalList">
        <div><dt>청구권 존재</dt><dd>{data.claimExistenceHint || '판단 불가'}</dd></div>
        <div><dt>입증 가능성</dt><dd>{data.factProvabilityHint || '판단 불가'}</dd></div>
        {limitation ? <div><dt>소멸시효 기산일</dt><dd>{limitation}</dd></div> : null}
        {data.submittedEvidenceTypes.length ? <div><dt>제출 증빙</dt><dd>{data.submittedEvidenceTypes.join(', ')}</dd></div> : null}
      </dl>
      {data.reviewNote ? <p className="reasonText">{data.reviewNote}</p> : null}
    </div>
  );
}

function ReliefExecutabilityTab({ data }) {
  if (!data) return <InlineEmptyNotice>표시할 정보 없음</InlineEmptyNotice>;
  return (
    <div className="reliefReviewBox">
      <p className="reliefReviewHead">
        <Gavel size={14} strokeWidth={2.2} className="sectionIcon" aria-hidden="true" />
        <span className="statusChip tone-info">신뢰도 {data.extractionConfidence || '불명확'}</span>
        <span className="statusChip tone-info">{data.debtorAssetStatus || '판단 불가'}</span>
      </p>
      {data.reviewNote ? <p className="reasonText">{data.reviewNote}</p> : null}
    </div>
  );
}

function ReliefAppropriatenessTab({ data }) {
  if (!data) return <InlineEmptyNotice>표시할 정보 없음</InlineEmptyNotice>;
  return (
    <div className="reliefReviewBox">
      <p className="reliefReviewHead">
        <Award size={14} strokeWidth={2.2} className="sectionIcon" aria-hidden="true" />
        <span className="statusChip tone-info">신뢰도 {data.extractionConfidence || '불명확'}</span>
        {data.personalMotiveFlags.map((flag) => <span key={flag} className="statusChip tone-danger">{flag}</span>)}
      </p>
      <dl className="reliefSignalList">
        <div><dt>사건 성격</dt><dd>{data.caseNature || '판단보류'}</dd></div>
        <div><dt>대안적 구제</dt><dd>{mentionLabel(data.alternativeReliefMentioned)}</dd></div>
        <div><dt>소액 청구</dt><dd>{mentionLabel(data.lowValueClaimMentioned)}</dd></div>
        {data.outOfScopeFlags.length ? <div><dt>범위 밖 사유</dt><dd>{data.outOfScopeFlags.join(', ')}</dd></div> : null}
      </dl>
      {data.reviewNote ? <p className="reasonText">{data.reviewNote}</p> : null}
    </div>
  );
}

// checklist_json(=relief_review_checklist)의 4개 신호를 탭으로 나눠 보여줍니다. eligibility만
// Rule Engine의 결론이고 나머지 셋(winnability/executability/appropriateness)은 LLM이 뽑아낸
// '판단 보조 신호'라 결론처럼 보이지 않게 헤더에 extractionConfidence(명시적/추정/불명확)를
// 같이 보여줍니다(eligibility 탭은 이 필드 자체가 없어 생략). detail이 없으면(옛 저장 데이터
// 등) 아무것도 렌더링하지 않습니다.
function ReliefReviewDetailTabs({ detail }) {
  const [activeTab, setActiveTab] = useState('eligibility');
  if (!detail) return null;

  const tabs = [
    { key: 'eligibility', label: '구조대상 여부', dot: false, icon: ShieldCheck },
    { key: 'winnability', label: '승소가능성', dot: detail.winnability?.statuteOfLimitationsFlag === '계산 불가', icon: TrendingUp },
    { key: 'executability', label: '집행가능성', dot: false, icon: Gavel },
    { key: 'appropriateness', label: '구조타당성', dot: (detail.appropriateness?.personalMotiveFlags || []).length > 0, icon: Award },
  ];

  return (
    <div>
      <div className="categoryTabs">
        {tabs.map((tab) => {
          const TabIcon = tab.icon;
          return (
            <button
              key={tab.key}
              type="button"
              className={activeTab === tab.key ? 'categoryTab active' : 'categoryTab'}
              onClick={() => setActiveTab(tab.key)}
            >
              <TabIcon size={13} strokeWidth={2.2} aria-hidden="true" />
              {tab.label}
              {tab.dot ? <span className="categoryTabDot" aria-hidden="true" /> : null}
            </button>
          );
        })}
      </div>
      {activeTab === 'eligibility' ? <ReliefEligibilityTab data={detail.eligibility} /> : null}
      {activeTab === 'winnability' ? <ReliefWinnabilityTab data={detail.winnability} /> : null}
      {activeTab === 'executability' ? <ReliefExecutabilityTab data={detail.executability} /> : null}
      {activeTab === 'appropriateness' ? <ReliefAppropriatenessTab data={detail.appropriateness} /> : null}
    </div>
  );
}

// 서식 초안 검토 상태(DocumentReviewStatus, backend/core-api)를 화면에 보여줄 라벨/톤으로 바꿉니다.
const DOCUMENT_STATUS_LABEL = {
  DRAFTED: '초안 작성됨 (검토 요청 전)',
  SUBMITTED_FOR_REVIEW: '변호사 검토 요청됨',
  APPROVED: '변호사 승인 완료',
  REVISION_REQUESTED: '반려됨 (수정 필요)',
};
function documentStatusTone(status) {
  if (status === 'APPROVED') return 'success';
  if (status === 'REVISION_REQUESTED') return 'danger';
  if (status === 'SUBMITTED_FOR_REVIEW') return 'info';
  return 'muted';
}

function generatedFileName(path = '') {
  if (!path) return '';
  const normalized = path.replace(/\\/g, '/');
  return normalized.split('/').filter(Boolean).at(-1) || path;
}

// label을 넘기면 그 문구를 표시 이름으로 쓰고(예: '조정신청서 초안 파일'), 안 넘기면 예전처럼
// 실제 저장 파일명을 그대로 보여줍니다. 서버가 생성하는 파일명은 사람이 알아보기 어려운 무작위
// 식별자라, 변호사 검토 화면처럼 이미 서식명을 알고 있는 곳에서는 label로 바꿔 보여주는 게 낫습니다.
// consultationId+documentId를 넘기면(=core-api에 실제 저장된 문서) 새로 생긴 다운로드 API로
// 진짜 파일을 받는 링크를 만듭니다. 없으면(로컬 전용 문서) 예전처럼 draft_file_path 자체를
// 링크로 쓸 수 있는지만 확인합니다(blob: URL 등).
// core-api가 인증을 요구하게 되면서 <a href>로는 더 이상 받을 수 없습니다. 브라우저가 주소만
// 열고 Authorization 헤더를 실어주지 않아 401이 나기 때문입니다.
// fetch로 받아 blob으로 만든 뒤, 그 blob을 가리키는 임시 링크를 클릭시켜 저장합니다.
// 사용자가 보는 동작(눌러서 내려받기)은 그대로입니다.
function ServerDocumentDownloadButton({ url, fileName, className = '' }) {
  const [downloading, setDownloading] = useState(false);
  const [error, setError] = useState('');
  if (!url) return null;

  const handleDownload = async () => {
    setDownloading(true);
    setError('');
    try {
      const response = await fetch(url, { headers: coreAuthHeader() });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const blob = await response.blob();
      const objectUrl = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = objectUrl;
      link.download = fileName || '첨부파일';
      document.body.appendChild(link);
      link.click();
      link.remove();
      // 브라우저가 저장을 시작할 시간을 준 뒤 해제합니다. 바로 지우면 받다 말고 끊깁니다.
      setTimeout(() => URL.revokeObjectURL(objectUrl), 10000);
    } catch (downloadError) {
      setError(`다운로드 실패 (${downloadError.message})`);
    } finally {
      setDownloading(false);
    }
  };

  return (
    <span className="serverDocumentDownload">
      <button type="button" className={className || undefined} onClick={handleDownload} disabled={downloading}>
        {downloading ? '내려받는 중…' : '다운로드'}
      </button>
      {error ? <span className="formError">{error}</span> : null}
    </span>
  );
}

// 서버에 저장된 파일이 없는 로컬 전용 초안(ai-api-local/text-local/client-hwpx 등)의 본문(draftText)으로
// 그 자리에서 새 HWPX 파일을 만들어 내려받게 합니다. createClientHwpxDraft는 클릭 시점에 매번 새
// blob: URL을 만들기 때문에(미리 만들어 저장해두지 않음), 세션이 바뀌어도 죽은 링크가 되지 않습니다.
function ClientHwpxDownloadButton({ templateName, draftText }) {
  const handleClick = () => {
    const { fileName, url } = createClientHwpxDraft({ templateName, draftText });
    const link = window.document.createElement('a');
    link.href = url;
    link.download = fileName;
    // 다운로드는 클릭 이벤트 이후 브라우저가 비동기로 처리합니다. click() 직후 바로
    // revokeObjectURL을 부르면 일부 브라우저(특히 Firefox)에서는 브라우저가 blob을 읽기도
    // 전에 URL이 무효화되어 다운로드가 실패합니다. 링크를 문서에 잠깐 붙였다 떼고,
    // revoke는 다음 tick으로 미뤄 다운로드가 실제로 시작된 뒤에 처리되게 합니다.
    window.document.body.appendChild(link);
    link.click();
    link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 0);
  };
  return (
    <span className="serverDocumentDownload">
      <button type="button" onClick={handleClick}>다운로드</button>
    </span>
  );
}

function GeneratedFileLink({ path, label, consultationId, documentId, content, downloadFileName }) {
  if (!path && !content) return null;

  const downloadUrl = consultationId && documentId
    ? buildCoreDocumentDownloadUrl(consultationId, documentId)
    : '';
  const rawFileName = label || downloadFileName || generatedFileName(path) || '\uC0DD\uC131 \uD30C\uC77C';
  const safeFileName = rawFileName.includes('?') ? '\uC0DD\uC131 \uD30C\uC77C' : rawFileName;

  if (downloadUrl) {
    return (
      <div className="generatedFileInline">
        <span>{safeFileName}</span>
        <ServerDocumentDownloadButton url={downloadUrl} fileName={safeFileName} />
      </div>
    );
  }

  if (content) {
    // 예전엔 여기가 "서버 파일 없음"이라는 읽기 전용 텍스트뿐이라, 로컬 전용 초안(서버에 실제
    // 파일이 없는 ai-api-local/text-local/client-hwpx 검토 건)은 검토자가 내려받을 방법이
    // 전혀 없었습니다. 본문(content)이 있으니 그걸로 바로 HWPX를 만들어 내려받게 합니다.
    return (
      <div className="generatedFileInline">
        <span>{safeFileName}</span>
        <ClientHwpxDownloadButton templateName={safeFileName} draftText={content} />
      </div>
    );
  }

  return (
    <div className="generatedFileInline">
      <span>{safeFileName}</span>
      <code>{path}</code>
    </div>
  );
}

function DraftContentReviewLabel({ content }) {
  if (!content) return null;
  return <span className="generatedFileInline">{'\uBCF8\uBB38 \uCD08\uC548 \uAC80\uD1A0'}</span>;
}

function normalizeGeneratedDocument(response = {}) {
  return {
    documentId: response.document_id || response.documentId || response.local_key,
    consultationId: response.consultation_id || response.consultationId || '',
    status: response.status || 'DRAFTED',
    formName: response.form_name || response.formName || '',
    requestedFormName: response.requested_form_name || response.requestedFormName || '',
    draftFilePath: response.draft_file_path || response.draftFilePath || response.file || '',
    downloadFileName: response.download_file_name || response.downloadFileName || '',
    draftContent: response.draft_content || response.draftContent || '',
    source: response.source || 'core-api',
    localKey: response.local_key || '',
  };
}

// 예전엔 서버가 돌려준 원문 예외 메시지(예: "I/O error on POST request for
// "http://localhost:8001/forms/draft": null")와 내부 서비스 이름('ai-api')을 그대로
// 보여줘서, 상담원이 읽어도 무엇을 해야 할지 알 수 없었습니다(코치 피드백: 개발자 용어를
// 유저 친화적으로). 원인을 알 수 있을 때만 짧게 덧붙이고, 항상 다음 행동을 안내합니다.
function draftGenerationErrorMessage(error) {
  const isConnectionIssue = /I\/O error|Connection refused|ECONNREFUSED|timeout/i.test(error?.message || '');
  const reason = isConnectionIssue ? ' · 서식 생성 서버에 연결하지 못했습니다' : '';
  return `HWPX 생성에 실패했습니다${reason}. 잠시 후 다시 시도하거나 관리자에게 문의해 주세요.`;
}

// consultationId를 넘기고 document가 core-api에 실제 저장된 것(source: 'core-api')이면 실제
// 다운로드 API(.../documents/{id}/download, GeneratedDocumentController)로 진짜 파일을 받는
// 버튼을 보여줍니다. 이 경우는 항상 다운로드로 응답하도록 백엔드가 고정돼 있어
// (Content-Disposition: attachment) '미리보기'는 의미가 없으므로 다운로드 버튼만 둡니다.
//
// 경우가 있는데, blob: URL은 그 blob을 만든 "이 페이지 세션"에서만 유효하고 새로고침하거나 나중에
// 다시 열면(변호사 검토 요청 후 다른 시점에 다시 여는 경우 등) 이미 죽어 있어 다운로드가
// "사이트에서 사용할 수 없는 파일" 오류로 항상 실패합니다. 그래서 draftContent(초안 본문 텍스트,
// localStorage에 같이 저장돼 세션이 바뀌어도 남아있음)가 있으면 옛 blob을 재사용하지 않고 매번
// draftContent조차 없을 때만(구버전에 저장된 문서 등) 예전 filePath를 그대로 시도합니다.
function GeneratedFileBox({ document, consultationId }) {
  const filePath = document?.draftFilePath || '';
  const downloadUrl = document?.source === 'core-api' && consultationId && document?.documentId
    ? buildCoreDocumentDownloadUrl(consultationId, document.documentId)
    : '';
  const fileName = document?.downloadFileName || generatedFileName(filePath) || `${document?.formName || '서식초안'}.hwpx`;

  return (
    <div className="generatedFileBox">
      <div className="generatedFileHeader">
        <strong><FileText size={16} strokeWidth={2.2} className="sectionIcon" aria-hidden="true" /> 생성 파일</strong>
        <span className={`statusChip ${downloadUrl ? 'tone-success' : document?.draftContent ? 'tone-warn' : 'tone-muted'}`}>
          {downloadUrl ? <CheckCircle2 size={13} strokeWidth={2.4} aria-hidden="true" /> : <XCircle size={13} strokeWidth={2.4} aria-hidden="true" />}
          {downloadUrl ? '서버 저장됨' : document?.draftContent ? '본문 기반 임시 파일' : '초안 없음'}
        </span>
        {downloadUrl ? (
          <div className="generatedFileActions">
            <ServerDocumentDownloadButton
              className="primaryButton compactAction"
              url={downloadUrl}
              fileName={fileName || 'document.hwpx'}
            />
          </div>
        ) : null}
      </div>
      {downloadUrl ? (
        <>
          <span><Download size={13} strokeWidth={2.2} aria-hidden="true" /> {fileName}을 서버에서 다운로드할 수 있습니다.</span>
          {filePath ? <code className="generatedFilePath">{filePath}</code> : null}
        </>
      ) : document?.draftContent ? (
        <>
          <span>서버 파일 없음 · 본문으로 임시 파일 생성</span>
          <ClientHwpxDownloadButton templateName={document.formName || fileName} draftText={document.draftContent} />
        </>
      ) : (
        <>
          <span>서버 HWPX 초안 없음</span>
          <button type="button" disabled>서버 파일 없음</button>
        </>
      )}
    </div>
  );
}

export { UtilityPanel, ReliefReviewSummary, ReliefReviewDetailTabs, DOCUMENT_STATUS_LABEL, documentStatusTone, GeneratedFileLink, DraftContentReviewLabel, SummaryBulletList };
