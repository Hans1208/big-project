import React, { useState, useEffect, useRef } from 'react';
import {
  ShieldCheck, ClipboardList, Info, Check, PhoneCall, FileSearch, Paperclip, EyeOff, BadgeCheck,
  Scale, ListChecks, Sparkles, Clock, Inbox, CheckCircle2, AlertTriangle,
} from 'lucide-react';
import { today } from '../../../constants.jsx';
import { useToast } from '../../../components/feedback.jsx';
import { CollapsibleSection, HitlConfirmModal, InlineEmptyNotice, WorkPageHeader, friendlyErrorMessage } from '../../../components/common.jsx';
import { caseCategories } from '../../../data/domain.js';
import { appendAuditLog } from '../../../services/storage.js';
import { validateAnalysisResult } from '../../../services/legalAidApi.js';
import {
  getCoreAnalysisJob,
  findActiveCoreAnalysisJob,
  isCoreConnectionError,
  mapCoreAnalysisResponse,
  submitCoreAnalysisForReview,
  timelineEmptyMessage,
  triggerCoreAnalysis,
  waitForCoreAnalysisJob,
} from '../../../services/coreApiClientV2.js';
import { readCachedFormRecommendations } from '../../../services/draftDocumentStore.js';
import { createRealtimeAudioStream, fetchAvailableAudioCalls } from '../../../services/realtimeAudioStream.js';
import { caseOptions, computeCaseEmergency, resolveEligibilityFromCase, emergencyReason, levelFromRatio, fitRatioToLevel } from '../shared/caseHelpers.js';
import {
  mergeContractAnalysisResponse,
  buildAnalysisResult,
  pickClientName,
  markAiLinkedSection,
  normalizeMissingInfoItems,
  localMissingDataSuggestions,
  buildAiResultSummary,
} from '../shared/analysisHelpers.js';
import { formatElapsed } from '../shared/formatters.js';
import { reviewActionTone, checklistItemNote, checklistItemFlag } from '../shared/reviewHelpers.js';
import { extractionStatusLabel, buildAttachmentLinkMetadata } from '../shared/attachmentHelpers.js';
import { CasePicker } from '../components/CasePicker.jsx';
import { ConsultationChannelTabs } from '../components/ConsultationChannelTabs.jsx';
import { SummaryBulletList } from '../components/SummaryBulletList.jsx';
import { RecommendedFormsPanel } from './RecommendedFormsPanel.jsx';
import { ReliefReviewDetailTabs } from '../relief/ReliefReviewDetailTabs.jsx';
import { ReliefLawyerSummaryCard } from '../relief/ReliefLawyerSummaryCard.jsx';

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
export function AnalysisWorkbench({ consultations, onCreateConsultation, onUpdateConsultation, onRequestLegalReview, onAnalysisSaved, currentUser, onGoToDashboard, onOpenDraft, focusedConsultationId, analysisRuns = {}, onStartAnalysis }) {
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
    // const refreshTimer = window.setInterval(() => {
    //   refreshAvailableAudioCalls({ silent: true });
    // }, 5000);
    // return () => window.clearInterval(refreshTimer);
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
        <ConsultationChannelTabs
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
