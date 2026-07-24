import React, { useEffect, useMemo, useState } from 'react';
import { ChevronLeft, ChevronRight } from 'lucide-react';
import { statusAll, today } from '../constants.jsx';
import { EmptyRows, StatusButton, SummaryCards, ConsultationTable, HitlConfirmModal, workflowStatusTone } from '../components/common.jsx';
import { UtilityPanel } from './workflows.jsx';
import { appendAuditLog, getAuditLogs } from '../services/storage.js';
import { checkTemplateRevision, simulateBackendLatency } from '../services/legalAidApi.js';
import { checkAiApiHealth } from '../services/aiApiClient.js';
import { checkCoreApiStatus } from '../services/coreApiClient.js';
import { caseCategories, getCaseCategory } from '../data/domain.js';
import { useAsyncAction } from '../components/loading.jsx';
import { statusChipClass } from '../utils/statusTone.js';

function CounselorDashboard({ consultations, setConsultations, onCreateConsultation, onRequestLegalReview, onAnalysisSaved, onDeleteConsultation, onOpenConsultationForm, onOpenAnalysis, onGoToDashboard, activeView, currentUser, onUpdateProfile, notifications, onReadNotifications, onDeleteNotification, onOpenNotification, focusedConsultationId }) {
  const [filter, setFilter] = useState(statusAll);
  const [selectedDate, setSelectedDate] = useState(today);
  const filtered = filter === statusAll ? consultations : consultations.filter((item) => item.status === filter);
  const dateRows = filtered.filter((item) => item.date === selectedDate);
  const cards = [
    { title: '총 상담', value: `${consultations.length}건`, filter: statusAll },
    { title: '진행 중인 상담', value: `${consultations.filter((item) => item.status === '진행 중').length}건`, filter: '진행 중' },
    { title: '완료된 상담', value: `${consultations.filter((item) => item.status === '완료').length}건`, filter: '완료' },
    { title: '보류 상담', value: `${consultations.filter((item) => item.status === '보류').length}건`, filter: '보류' },
  ];
  const reworkRows = consultations.filter((item) => item.reviewAction && !item.reviewAction.resolved);

  if (activeView !== '대시보드') {
    return <UtilityPanel view={activeView} role="counselor" consultations={consultations} onCreateConsultation={onCreateConsultation} onRequestLegalReview={onRequestLegalReview} onAnalysisSaved={onAnalysisSaved} onUpdateConsultation={(id, updates) => setConsultations((items) => items.map((item) => item.id === id ? { ...item, ...updates } : item))} currentUser={currentUser} onUpdateProfile={onUpdateProfile} onGoToDashboard={onGoToDashboard} notifications={notifications} onReadNotifications={onReadNotifications} onDeleteNotification={onDeleteNotification} onOpenNotification={onOpenNotification} focusedConsultationId={focusedConsultationId} />;
  }
  return (
    <main className="dashboard dashboard-counselor">
      <section className="dashboardLeft">
        <SummaryCards cards={cards} activeFilter={filter} onFilter={setFilter} />
        <ConsultationTable title={filter === statusAll ? '최근 상담 목록' : `${filter} 상담 목록`} rows={filtered} onAdd={onOpenConsultationForm} onDelete={onDeleteConsultation} onOpenAnalysis={onOpenAnalysis} searchable />
      </section>
      <section className="dashboardRight">
        <div className="counselorTopSlot">
          <CounselorReworkPanel rows={reworkRows} onOpenAnalysis={onOpenAnalysis} />
        </div>
        <ConsultationTable title="일정별 상담 목록" rows={dateRows} onDelete={onDeleteConsultation} onOpenAnalysis={onOpenAnalysis} tall selectedDate={selectedDate} onDateChange={setSelectedDate} />
      </section>
    </main>
  );
}

function CounselorReworkPanel({ rows, onOpenAnalysis }) {
  return (
    <section className="panel reworkPanel">
      <div className="panelTitleRow"><h2>보완 요청 상담</h2></div>
      {rows.length ? (
        <div className="reworkList">
          {rows.map((row) => (
            <article className="reworkItem" key={row.id}>
              <div>
                <strong>{row.caseNo} {row.title}</strong>
                <p><span>{row.reviewAction.status}</span>{row.reviewAction.reason || '사유가 입력되지 않았습니다.'}</p>
                {row.eligibilityCheck?.isTargetCandidate && !row.eligibilityCheck?.evidenceSubmitted ? (
                  <p className="missingEvidenceLine">미제출 증빙: {row.eligibilityCheck.requiredEvidence}</p>
                ) : null}
              </div>
              <button className="tableAction reviewActionButton" type="button" onClick={() => onOpenAnalysis?.(row.id)}>수정 진행</button>
            </article>
          ))}
        </div>
      ) : (
        <p className="reworkEmptyNotice">변호사 검토 후 다시 처리할 상담이 없습니다.</p>
      )}
    </section>
  );
}

function LawyerDashboard({ reviews, setReviews, onReviewDecision, onGoToDashboard, activeView, currentUser, onUpdateProfile, notifications, onReadNotifications, onDeleteNotification, onOpenNotification, onNotify, focusedReviewCaseNo }) {
  const [filter, setFilter] = useState(statusAll);
  const [logs, setLogs] = useState([]);
  const [activeReview, setActiveReview] = useState(null);
  const filtered = filter === statusAll ? reviews : reviews.filter((item) => item.status === filter);
  useEffect(() => {
    if (!focusedReviewCaseNo) return;
    const target = reviews.find((item) => item.caseNo === focusedReviewCaseNo);
    if (target) {
      setFilter(statusAll);
      setActiveReview(target);
    }
  }, [activeView, focusedReviewCaseNo, reviews]);
  const cards = [
    { title: '검토 대기', value: `${reviews.filter((item) => item.status === '검토 대기').length}건`, filter: '검토 대기' },
    { title: '검토 중', value: `${reviews.filter((item) => item.status === '검토 중').length}건`, filter: '검토 중' },
    { title: '승인 완료', value: `${reviews.filter((item) => item.status === '승인').length}건`, filter: '승인' },
    { title: '반려 처리', value: `${reviews.filter((item) => item.status === '반려').length}건`, filter: '반려' },
  ];
  // HITL 최종 결정: 결정(status)과 사유(reason)를 함께 기록하고 감사 로그로 남깁니다.
  const decideReview = (id, status, reason, recipientEmail) => {
    const target = reviews.find((item) => item.id === id);
    const reviewerInfo = {
      name: currentUser?.name || '변호사',
      email: currentUser?.email || '',
      organization: currentUser?.organization || '',
    };
    const recipient = recipientEmail || target?.counselor?.email || '';
    setReviews((items) => items.map((item) => item.id === id ? { ...item, status, reason: reason || '', lawyer: reviewerInfo, recipientEmail: recipient } : item));
    onReviewDecision?.({
      id,
      status,
      reason,
      reviewer: reviewerInfo,
      recipientEmail: recipient,
    });
    if (target) setLogs((items) => [{ ...target, status, reason: reason || '', loggedAt: today }, ...items]);
    appendAuditLog({
      actor: currentUser?.email || '변호사',
      action: `법률구조 검토 결정: ${status}`,
      target: target?.caseNo || String(id),
      metadata: {
        reason: reason || '',
        lawyer: reviewerInfo.name,
        title: target?.title || '',
        caseType: target?.type || '',
      },
    });
    if (target && onNotify) {
      onNotify({
        roles: 'counselor',
        title: `검토 결과: ${status}`,
        message: `${target.caseNo} ${target.title}${reason ? ` / ${reason}` : ''}`,
        target: target.caseNo,
        recipientEmail: recipient,
      });
    }
    setActiveReview(null);
  };

  if (activeView !== '대시보드') {
    const reviewConsultations = reviews.map((item) => ({
      id: item.id,
      caseNo: item.caseNo,
      title: item.title,
      type: item.type,
      status: item.status,
      date: item.requestedAt,
      memo: `${item.title} 검토 요청`,
      attachments: [],
      logs: [],
    }));
    return <UtilityPanel view={activeView} role="lawyer" currentUser={currentUser} onUpdateProfile={onUpdateProfile} consultations={reviewConsultations} onUpdateConsultation={() => {}} onCreateConsultation={() => {}} onGoToDashboard={onGoToDashboard} notifications={notifications} onReadNotifications={onReadNotifications} onDeleteNotification={onDeleteNotification} onOpenNotification={onOpenNotification} />;
  }
  return (
    <main className="dashboard dashboard-lawyer">
      <section className="dashboardLeft"><SummaryCards cards={cards} activeFilter={filter} onFilter={setFilter} /><ReviewLog logs={logs} /></section>
      <section className="dashboardRight"><ReviewTable rows={filtered} onOpenReview={setActiveReview} /></section>
      {activeReview ? (
        <HitlDecisionModal
          review={activeReview}
          reviewer={currentUser?.name || '변호사'}
          onDecide={decideReview}
          onClose={() => setActiveReview(null)}
        />
      ) : null}
    </main>
  );
}

// 검토 상태도 상담 상태와 같은 색 기준(statusTone)을 그대로 씁니다. (색상 일관성)
const reviewStatusTone = statusChipClass;

function ReviewTable({ rows, onOpenReview }) {
  return (
    <section className="panel">
      <div className="panelTitleRow"><h2>법률구조 검토 요청</h2></div>
      <table className="dataTable">
        <thead><tr><th>상담 번호</th><th>유형</th><th>사건 제목</th><th>상태</th><th>검토</th></tr></thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.id}>
              <td>{row.caseNo}</td><td>{row.type}</td><td>{row.title}</td>
              <td><span className={reviewStatusTone(row.status)}>{row.status}</span></td>
              {/* HITL: 결정을 바로 누르지 않고 검토 모달을 열어 AI 결과 확인 후 사유와 함께 확정합니다. */}
              <td><button className="tableAction reviewActionButton" type="button" onClick={() => onOpenReview(row)}>{row.status === '검토 대기' || row.status === '검토 중' ? '검토하기' : '재검토하기'}</button></td>
            </tr>
          ))}
          <EmptyRows count={Math.max(0, 6 - rows.length)} columns={5} />
        </tbody>
      </table>
    </section>
  );
}

// 법률구조 HITL(Human-in-the-loop) 최종 결정 모달.
// AI 분석은 참고용이고, 변호사/공익법무관이 법률 판단 항목을 확인한 뒤 결정과 사유를 확정합니다.
const hitlDecisions = [
  { key: '승인', label: '승인', hint: '법률구조 대상으로 확정하고 다음 단계로 진행', tone: 'success', needsReason: false },
  { key: '수정 요청', label: '수정 요청', hint: '상담원에게 서식·내용 수정을 요청 (사유 필수)', tone: 'warn', needsReason: true },
  { key: '추가자료 요청', label: '추가자료 요청', hint: '판단에 필요한 자료 보완을 요청 (사유 필수)', tone: 'warn', needsReason: true },
  { key: '반려', label: '반려', hint: '구조 대상 부적합으로 거절 (사유 필수)', tone: 'danger', needsReason: true },
  { key: '보류', label: '보류', hint: '추가 검토가 필요해 결정을 보류 (사유 필수)', tone: 'warn', needsReason: true },
];

function formatAnalysisList(items, emptyText) {
  return Array.isArray(items) && items.length ? items : [emptyText];
}

function fileExtractionLabel(status) {
  const labels = { success: '추출 성공', empty: '내용 없음', unsupported: '미지원', failed: '처리 실패' };
  return labels[status] || status || '상태 미확인';
}

function HitlDecisionModal({ review, reviewer, onDecide, onClose }) {
  const [decision, setDecision] = useState('');
  const [reason, setReason] = useState('');
  const [recipientEmail, setRecipientEmail] = useState(review.counselor?.email || '');
  const [checks, setChecks] = useState({ eligibility: false, evidence: false, hallucination: false });
  const [showFinalHitlConfirm, setShowFinalHitlConfirm] = useState(false);
  const selectedDecision = hitlDecisions.find((item) => item.key === decision);
  const analysis = review.analysis || {};
  const adoptedItems = formatAnalysisList(analysis.adoptedItems, '상담원이 채택한 검토 반영 항목 없음');
  const timelineItems = formatAnalysisList(analysis.timeline, { date: '-', text: '정리된 사실관계 타임라인 없음' });
  const extractedItems = formatAnalysisList(analysis.extractionDetail, { status: '', fileLink: '', note: '첨부파일 추출 정보 없음' });
  const attachmentItems = formatAnalysisList(analysis.sourceAttachments?.length ? analysis.sourceAttachments : analysis.extractedJson?.attachment_links, { fileName: '첨부 링크 정보 없음', fileKey: '', fileUrl: '' });
  const modalityItems = formatAnalysisList(analysis.modalities, { key: '입력자료', count: 0 });
  const sttOriginal = analysis.sttPreview?.original || 'STT 원문 정보가 없습니다.';
  const sttMasked = analysis.sttPreview?.masked || '마스킹본 정보가 없습니다.';
  const allChecked = checks.eligibility && checks.evidence && checks.hallucination;
  const trimmedReason = reason.trim();
  const reasonRequired = selectedDecision?.needsReason && !trimmedReason;
  const canSubmit = decision && allChecked && !reasonRequired;
  const completeDecision = () => {
    setShowFinalHitlConfirm(false);
    onDecide(review.id, decision, trimmedReason, recipientEmail);
  };

  return (
    <div className="modalBackdrop" role="presentation">
      <div className="modal hitlModal">
        <div className="modalHeader"><h2>법률구조 최종 검토</h2><button type="button" onClick={onClose}>닫기</button></div>

        <div className="hitlCaseMeta">
          <span><strong>{review.caseNo}</strong></span>
          <span>{review.type}</span>
          <span>{review.title}</span>
        </div>
        <div className="reviewRecipientBox">
          <div>
            <strong>담당 상담원</strong>
            <span>
              {review.counselor?.name || '미지정'}
              {review.counselor?.organization ? ` · ${review.counselor.organization}` : ''}
            </span>
          </div>
          <label>
            검토 결과 수신
            <select value={recipientEmail} onChange={(event) => setRecipientEmail(event.target.value)}>
              <option value={review.counselor?.email || ''}>
                {review.counselor?.email ? `${review.counselor.name || '담당 상담원'} (${review.counselor.email})` : '담당 상담원 미지정'}
              </option>
            </select>
          </label>
        </div>

        {/* AI 분석은 참고용임을 명확히 (HITL 원칙) */}
        <div className="hitlBanner">아래 AI 분석은 참고용입니다. 법률 판단 항목을 직접 확인하신 뒤 최종 결정을 확정해주세요.</div>

        <div className="hitlSection">
          <h3>상담원 분석 내용</h3>
          <div className="resultCard lawyerAnalysisCard">
            <div className="lawyerAnalysisHeader">
              <strong>검토 요청에 포함된 상담 분석 패키지</strong>
              <span>상담원이 저장한 AI 분석·보완자료·채택 항목을 기준으로 최종 판단합니다.</span>
            </div>
            <p>{analysis.summary || review.summary || '상담원이 저장한 분석 요약이 없습니다.'}</p>
            <div className="hitlAnalysisGrid">
              <span>사건 유형: {analysis.caseType || review.type}</span>
              <span>긴급도: {analysis.urgency || review.urgency || '중'}</span>
              <span>구조대상: {analysis.eligibility || review.eligibility || '검토 필요'}</span>
            </div>
            {analysis.counselorReviewNote ? <pre className="counselorReviewNote">{analysis.counselorReviewNote}</pre> : null}
            {analysis.caseTypeReason ? <p className="reasonText">분류 근거: {analysis.caseTypeReason}</p> : null}
            {analysis.emergency?.reason ? <p className="reasonText">긴급도 근거: {analysis.emergency.reason}</p> : null}
            {analysis.eligibilityCheck ? (
              <div className={analysis.eligibilityCheck.isTargetCandidate && !analysis.eligibilityCheck.evidenceSubmitted ? 'eligibilitySummary missingEvidence' : 'eligibilitySummary'}>
                <span>대상 유형: {analysis.eligibilityCheck.applicantType}</span>
                <span>필요 증빙: {analysis.eligibilityCheck.requiredEvidence}</span>
                <span>증빙 제출: {analysis.eligibilityCheck.evidenceSubmitted ? '확인됨' : '미제출'}</span>
              </div>
            ) : null}
          </div>
        </div>

        <div className="hitlSection">
          <h3>누락 자료·체크리스트</h3>
          <div className="resultCard hitlEvidenceGrid">
            <div>
              <strong>누락 자료</strong>
              {analysis.missingInfo?.length ? analysis.missingInfo.map((item) => (
                <span key={item}>
                  {item}
                  {analysis.evidenceStatus?.[item] ? ` · ${analysis.evidenceStatus[item] === 'submitted' ? '제출 확인' : '미제출'}` : ''}
                </span>
              )) : <span>표시된 누락 자료 없음</span>}
            </div>
            <div>
              <strong>상담원 확인 항목</strong>
              {analysis.checklist?.length ? analysis.checklist.map((item) => <span key={item.label}>{item.checked ? '확인' : '미확인'} · {item.label}</span>) : <span>체크리스트 없음</span>}
            </div>
          </div>
        </div>

        <div className="hitlSection">
          <h3>STT 개인정보 마스킹</h3>
          <div className="resultCard lawyerSttGrid">
            <div>
              <strong>마스킹본</strong>
              <p>{sttMasked}</p>
            </div>
            <div>
              <strong>원문</strong>
              <p>{sttOriginal}</p>
              <span>원문에는 민감정보가 포함될 수 있으므로 검증 목적으로만 확인합니다.</span>
            </div>
          </div>
        </div>

        <div className="hitlSection">
          <h3>검토 근거 상세</h3>
          <div className="resultCard lawyerEvidenceBundle">
            <div>
              <strong>상담원 채택 항목</strong>
              {adoptedItems.map((item) => <span key={typeof item === 'string' ? item : item.text}>{typeof item === 'string' ? item : item.text}</span>)}
            </div>
            <div>
              <strong>입력자료 구성</strong>
              {modalityItems.map((item) => <span key={item.key}>{item.key}: {item.count}건</span>)}
            </div>
            <div>
              <strong>첨부파일 추출 상태</strong>
              {extractedItems.map((item, index) => (
                <span key={`${item.fileLink || item.note}-${index}`}>
                  {fileExtractionLabel(item.status)} · {item.fileLink || item.note || '파일명 없음'}
                </span>
              ))}
            </div>
            <div>
              <strong>첨부 저장 위치</strong>
              {attachmentItems.map((item, index) => {
                const location = item.fileKey || item.fileUrl || item.fileName || '저장 위치 없음';
                return (
                  <span key={`${location}-${index}`}>
                    {item.fileName || '첨부파일'} · {location}
                  </span>
                );
              })}
            </div>
            <div>
              <strong>AI 응답 검증</strong>
              <span>형식: {analysis.verification?.format ? '통과' : '확인 필요'}</span>
              <span>근거: {analysis.verification?.grounded ? '첨부자료 근거 확인' : '근거 보강 필요'}</span>
              <span>환각 위험: {analysis.verification?.hallucinationRisk ? '확인 필요' : '낮음'}</span>
            </div>
          </div>
        </div>

        <div className="hitlSection">
          <h3>사실관계 타임라인</h3>
          <div className="resultCard lawyerTimeline">
            {timelineItems.map((item, index) => (
              <span key={`${item.date}-${item.text}-${index}`}>
                <strong>{item.date || '-'}</strong>
                {item.text || item}
              </span>
            ))}
          </div>
        </div>

        <div className="hitlSection">
          <h3>법률 판단 항목 확인</h3>
          <div className="resultCard checklistBox">
            <label><input type="checkbox" checked={checks.eligibility} onChange={() => setChecks((c) => ({ ...c, eligibility: !c.eligibility }))} />법률구조 대상 요건을 확인했습니다.</label>
            <label><input type="checkbox" checked={checks.evidence} onChange={() => setChecks((c) => ({ ...c, evidence: !c.evidence }))} />제출된 자료·증빙을 확인했습니다.</label>
            <label><input type="checkbox" checked={checks.hallucination} onChange={() => setChecks((c) => ({ ...c, hallucination: !c.hallucination }))} />AI가 제시한 법령·판례 근거의 실재 여부를 확인했습니다.</label>
          </div>
        </div>

        <div className="hitlSection">
          <h3>검토 결과 선택</h3>
          <div className="hitlDecisionGrid">
            {hitlDecisions.map((item) => (
              <button
                key={item.key}
                type="button"
                className={`hitlDecisionCard tone-${item.tone}${decision === item.key ? ' selected' : ''}`}
                onClick={() => setDecision(item.key)}
              >
                <strong>{item.label}</strong>
                <small>{item.hint}</small>
              </button>
            ))}
          </div>
        </div>

        {selectedDecision?.needsReason ? (
          <label className="field">
            <span>사유 <strong className="requiredMark">필수</strong></span>
            <textarea value={reason} onChange={(event) => setReason(event.target.value)} placeholder="사유를 입력하세요." />
          </label>
        ) : null}

        {reasonRequired ? <p className="formError">{decision} 결정에는 사유 입력이 필요합니다.</p> : null}
        {decision && !allChecked ? <p className="formError">법률 판단 항목을 모두 확인해야 결정을 확정할 수 있습니다.</p> : null}

        <div className="inlineControls statusConfirmActions">
          <button className="smallButton light" type="button" onClick={onClose}>취소</button>
          <button className="primaryButton hitlSubmitButton" type="button" disabled={!canSubmit} onClick={() => setShowFinalHitlConfirm(true)}>검토 확정</button>
        </div>
        <p className="helperText">결정자: {reviewer} · 확정하면 감사 로그와 담당 상담원 알림에 반영됩니다.</p>
        {showFinalHitlConfirm ? (
          <HitlConfirmModal
            title="검토 결과 확정 전 최종 확인"
            actionLabel="확인 후 확정"
            caseInfo={`${review.caseNo} · ${review.title} · ${decision}`}
            onConfirm={completeDecision}
            onCancel={() => setShowFinalHitlConfirm(false)}
          />
        ) : null}
      </div>
    </div>
  );
}

function ReviewLog({ logs }) {
  return (
    <section className="panel">
      <div className="panelTitleRow"><h2>최근 검토 결정 로그</h2></div>
      <table className="dataTable">
        <thead><tr><th>검토 번호</th><th>사건 번호</th><th>상담 제목</th><th>처리일</th><th>결정</th><th>사유</th></tr></thead>
        <tbody>
          {logs.slice(0, 6).map((row) => <tr key={`${row.id}-${row.status}-${row.loggedAt}`}><td>R-{row.id}</td><td>{row.caseNo}</td><td>{row.title}</td><td>{row.loggedAt}</td><td><span className={reviewStatusTone(row.status)}>{row.status}</span></td><td>{row.reason || '-'}</td></tr>)}
          <EmptyRows count={Math.max(0, 6 - logs.length)} columns={6} />
        </tbody>
      </table>
    </section>
  );
}

const roleLabels = { counselor: '상담원', lawyer: '변호사', admin: '관리자' };

function AdminDashboard({ users, onUpdateUserStatus, consultations, reviews, activeView, currentUser, onUpdateProfile, notifications, onReadNotifications, onDeleteNotification, onOpenNotification }) {
  const [activeAdminView, setActiveAdminView] = useState('consultations');
  // 관리자 자신을 포함해 전체 회원가입 신청자를 대상으로 승인 현황을 관리합니다.
  const userFilter = activeAdminView === 'pendingUsers' ? '대기' : activeAdminView === 'activeUsers' ? '승인' : statusAll;
  const filteredUsers = userFilter === statusAll ? users : users.filter((item) => item.status === userFilter);
  const cards = [
    { title: '전체 상담 건수', value: `${consultations.length}건`, filter: 'consultations' },
    { title: '활성 사용자', value: `${users.filter((item) => item.status === '승인').length}명`, filter: 'activeUsers' },
    { title: '분석 처리율', value: `${reviews.length ? Math.round((reviews.filter((item) => item.status === '승인').length / reviews.length) * 100) : 0}%`, filter: 'analysis' },
    { title: '직원 승인 대기', value: `${users.filter((item) => item.status === '대기').length}건`, filter: 'pendingUsers' },
  ];

  // 관리자 업무 범위(전체 조회/계정 권한 관리/통계 대시보드/DB 관리/감사로그)에는
  // 상담 등록이나 서식 초안 생성이 포함되지 않으므로, 그 메뉴들은 관리자 네비게이션에서 아예 제외했습니다.
  // (상담원/변호사 전용 워크벤치가 실수로라도 노출되지 않도록 여기서도 대시보드/프로필/운영관리/알림 4가지만 분기합니다.)
  if (activeView === '프로필') return <UtilityPanel view={activeView} role="admin" currentUser={currentUser} onUpdateProfile={onUpdateProfile} />;
  if (activeView === '기타') return <AdminOpsPanel />;
  if (activeView === '알림') return <UtilityPanel view={activeView} role="admin" currentUser={currentUser} notifications={notifications} onReadNotifications={onReadNotifications} onDeleteNotification={onDeleteNotification} onOpenNotification={onOpenNotification} />;
  return (
    <main className="dashboard dashboard-admin">
      <SummaryCards cards={cards} activeFilter={activeAdminView} onFilter={setActiveAdminView} allowToggle={false} />
      {activeAdminView === 'consultations' ? (
        <div className="adminSplit">
          <ConsultationStatsPanel consultations={consultations} />
          <BarChartMock consultations={consultations} />
        </div>
      ) : null}
      {activeAdminView === 'analysis' ? (
        <div className="adminSplit">
          <AnalysisStatsPanel reviews={reviews} />
          <DonutChartMock reviews={reviews} />
        </div>
      ) : null}
      {activeAdminView === 'activeUsers' ? <ActiveUsersPanel users={users} /> : null}
      {activeAdminView === 'pendingUsers' ? <AccountTable rows={filteredUsers} onUpdate={onUpdateUserStatus} title="회원가입 승인 대기" /> : null}
    </main>
  );
}

// 활성(승인된) 사용자 요약 패널. 역할별 인원 수와 계정 목록(이름/소속/이메일/가입 신청일)을 함께 보여줍니다.
function ActiveUsersPanel({ users }) {
  const approved = users.filter((user) => user.status === '승인');
  const roleOrder = ['counselor', 'lawyer', 'admin'];
  const roleCounts = roleOrder.map((role) => ({
    role,
    label: roleLabels[role],
    count: approved.filter((user) => user.role === role).length,
  }));

  return (
    <section className="panel activeUsersPanel">
      <div className="panelTitleRow"><h2>활성 사용자 현황</h2><span className="panelCountBadge">총 {approved.length}명</span></div>
      <div className="roleCountRow">
        {roleCounts.map((item) => (
          <div className={`roleCountChip role-${item.role}`} key={item.role}>
            <strong>{item.count}명</strong>
            <span>{item.label}</span>
          </div>
        ))}
      </div>
      <table className="dataTable">
        <thead><tr><th>이름</th><th>역할</th><th>소속기관 / 부서</th><th>지부</th><th>연락처</th><th>이메일</th><th>가입 신청일</th></tr></thead>
        <tbody>
          {approved.map((row) => (
            <tr key={row.email}>
              <td>{row.name}</td>
              <td>{roleLabels[row.role] || row.role}</td>
              <td>{row.organization || '-'}</td>
              <td>{row.branch || '-'}</td>
              <td>{row.phone || '-'}</td>
              <td>{row.email}</td>
              <td>{row.requestedAt || '-'}</td>
            </tr>
          ))}
          <EmptyRows count={Math.max(0, 6 - approved.length)} columns={7} />
        </tbody>
      </table>
    </section>
  );
}

function AccountTable({ rows, onUpdate, title = '회원가입 승인 관리', compact = false }) {
  return (
    <section className="panel">
      <div className="panelTitleRow"><h2>{title}</h2></div>
      <table className="dataTable">
        <thead><tr><th>이름</th><th>신청 역할</th>{compact ? null : <th>소속</th>}<th>이메일</th>{compact ? null : <th>신청일</th>}<th>승인/거절</th></tr></thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.email}>
              <td>{row.name}</td><td>{roleLabels[row.role] || row.role}</td>{compact ? null : <td>{row.organization}</td>}<td>{row.email}</td>{compact ? null : <td>{row.requestedAt}</td>}
              {/* 관리자만 상담원/변호사 계정을 승인·거절할 수 있고, 승인 전에는 로그인이 막힙니다. */}
              <td><div className="statusActions"><StatusButton active={row.status === '승인'} onClick={() => onUpdate(row.email, '승인')}>승인</StatusButton><StatusButton active={row.status === '거절'} onClick={() => onUpdate(row.email, '거절')}>거절</StatusButton></div></td>
            </tr>
          ))}
          <EmptyRows count={Math.max(0, 3 - rows.length)} columns={compact ? 4 : 6} />
        </tbody>
      </table>
    </section>
  );
}

const weekdayLabels = ['일', '월', '화', '수', '목', '금', '토'];

function toIsoDateLocal(date) {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

// 기준일(today)이 속한 주의 일요일을 구하고, weekOffset(주 단위)만큼 이동시킵니다.
function getWeekStart(weekOffset) {
  const base = new Date(today);
  base.setDate(base.getDate() - base.getDay() + weekOffset * 7);
  base.setHours(0, 0, 0, 0);
  return base;
}

function formatWeekRangeLabel(weekStart) {
  const weekEnd = new Date(weekStart);
  weekEnd.setDate(weekEnd.getDate() + 6);
  const fmt = (date) => `${date.getMonth() + 1}.${date.getDate()}`;
  return `${weekStart.getFullYear()}년 ${fmt(weekStart)} ~ ${fmt(weekEnd)}`;
}

// 이 화면의 막대그래프들(요일별 상담 건수, 사건 유형별 상담 건수)이 공용으로 쓰는 눈금 계산입니다.
// 실제 최댓값을 그대로 100%로 잡으면 건수가 적을 때는 막대가 꽉 차 보이고, 건수가 아주 많아지면
// 반대로 눈금 갱신이 안 따라가는 문제가 생깁니다. 그래서 최댓값의 3배 정도를 목표로 잡고
// 1/2/5/10 단위의 "보기 좋은 눈금"으로 올림해서, 하루 2건이든 법률구조공단 실제 규모(하루 수십~백여 건)든
// 막대가 항상 절제된(대략 20~35%대) 비율로 표현되도록 합니다.
function computeNiceScaleMax(rawMax) {
  if (rawMax <= 0) return 10;
  const headroomMultiplier = 3;
  const targetMax = rawMax * headroomMultiplier;
  const magnitude = 10 ** Math.floor(Math.log10(targetMax));
  const normalized = targetMax / magnitude;
  const niceNormalized = normalized <= 1 ? 1 : normalized <= 2 ? 2 : normalized <= 5 ? 5 : 10;
  return niceNormalized * magnitude;
}

function ConsultationStatsPanel({ consultations }) {
  const [weekOffset, setWeekOffset] = useState(0);
  const [selectedDate, setSelectedDate] = useState(today);

  const weekStart = useMemo(() => getWeekStart(weekOffset), [weekOffset]);
  const days = useMemo(() => weekdayLabels.map((label, index) => {
    const date = new Date(weekStart);
    date.setDate(date.getDate() + index);
    const iso = toIsoDateLocal(date);
    return {
      label,
      iso,
      dayOfMonth: date.getDate(),
      monthNum: date.getMonth() + 1,
      year: date.getFullYear(),
      closed: index === 0 || index === 6,
      isToday: iso === today,
      count: consultations.filter((item) => item.date === iso).length,
    };
  }), [weekStart, consultations]);
  const scaleMax = computeNiceScaleMax(Math.max(0, ...days.map((item) => item.count)));

  // 주를 이동하면 선택된 날짜가 화면에 보이는 주 밖으로 벗어나므로, 같은 요일로 자동 재선택합니다.
  useEffect(() => {
    const selectedWeekday = new Date(selectedDate).getDay();
    const matched = days.find((item) => new Date(item.iso).getDay() === selectedWeekday);
    if (matched && matched.iso !== selectedDate) setSelectedDate(matched.iso);
  }, [weekStart]); // eslint-disable-line react-hooks/exhaustive-deps

  const selectedDay = days.find((item) => item.iso === selectedDate) || days[0];
  const dayRows = consultations.filter((item) => item.date === selectedDay.iso);

  return (
    <section className="panel consultationStatsPanel">
      <div className="panelTitleRow consultationStatsHeader">
        <h2>전체 상담 현황</h2>
        <div className="weekNav">
          <button type="button" className="weekNavButton" onClick={() => setWeekOffset((value) => value - 1)} aria-label="이전 주"><ChevronLeft size={16} /></button>
          <span>{formatWeekRangeLabel(weekStart)}</span>
          <button type="button" className="weekNavButton" onClick={() => setWeekOffset((value) => value + 1)} aria-label="다음 주"><ChevronRight size={16} /></button>
          {/* 항상 노출해 컨트롤 폭을 고정합니다. 이번 주를 보고 있어도 선택 날짜를 오늘로 되돌립니다. */}
          <button
            type="button"
            className="weekNavToday"
            onClick={() => { setWeekOffset(0); setSelectedDate(today); }}
          >
            오늘
          </button>
        </div>
      </div>
      <div className="weekdayStats">
        {days.map((item) => (
          <button
            type="button"
            key={item.iso}
            className={[
              'weekdayStat',
              item.closed ? 'closed' : '',
              item.iso === selectedDay.iso ? 'selected' : '',
              item.isToday ? 'isToday' : '',
            ].filter(Boolean).join(' ')}
            onClick={() => setSelectedDate(item.iso)}
          >
            <span>{item.label} <em>{item.dayOfMonth}</em></span>
            <div className="weekdayBarTrack">
              {item.closed ? <em className="closedLabel">휴무</em> : <i style={{ height: `${item.count ? Math.max(14, (item.count / scaleMax) * 100) : 0}%` }} />}
            </div>
            <strong>{item.closed ? '상담 없음' : `${item.count}건`}</strong>
          </button>
        ))}
      </div>
      <div className="adminTableScroll">
        <table className="dataTable adminConsultationTable">
          <thead>
            <tr>
              <th colSpan={7} className="adminTableCaption">
                {selectedDay.closed ? `${selectedDay.label}요일 (휴무) 상담 내역` : `${selectedDay.year}.${selectedDay.monthNum}.${selectedDay.dayOfMonth} (${selectedDay.label}) 상담 내역 · ${dayRows.length}건`}
              </th>
            </tr>
            <tr><th>사건 번호</th><th>상담자</th><th>담당 상담원</th><th>검토 변호사</th><th>사건 유형</th><th>등록일</th><th>처리 단계</th></tr>
          </thead>
          <tbody>
            {dayRows.map((row) => <tr key={row.id}><td>{row.caseNo}</td><td>{row.name}</td><td>{row.counselor?.name || '미지정'}</td><td>{row.lawyer?.name || row.reviewAction?.reviewer?.name || '미지정'}</td><td>{row.type}</td><td>{row.date}</td><td><span className={workflowStatusTone(row.workflowStatus)}>{row.workflowStatus || '분석 전'}</span></td></tr>)}
            <EmptyRows count={Math.max(0, 5 - dayRows.length)} columns={7} />
          </tbody>
        </table>
      </div>
    </section>
  );
}

function AnalysisStatsPanel({ reviews }) {
  return (
    <section className="panel">
      <div className="panelTitleRow"><h2>분석 처리 상세</h2></div>
      <table className="dataTable">
        <thead><tr><th>사건 번호</th><th>사건 제목</th><th>상태</th><th>요청일</th></tr></thead>
        <tbody>
          {reviews.map((row) => <tr key={row.id}><td>{row.caseNo}</td><td>{row.title}</td><td><span className={reviewStatusTone(row.status)}>{row.status}</span></td><td>{row.requestedAt}</td></tr>)}
          <EmptyRows count={Math.max(0, 5 - reviews.length)} columns={4} />
        </tbody>
      </table>
    </section>
  );
}

function AdminOpsPanel() {
  const [templateStatus, setTemplateStatus] = useState('검사 전');
  const [auditRows, setAuditRows] = useState(() => getAuditLogs());
  const [aiApiStatus, setAiApiStatus] = useState({ tone: 'muted', label: '확인 전' });
  const [coreApiStatus, setCoreApiStatus] = useState({ tone: 'muted', label: '확인 전', users: 0, consultations: 0 });
  const runWithLoading = useAsyncAction();
  const runTemplateCheck = async () => {
    await runWithLoading(async () => {
      await simulateBackendLatency();
      const result = checkTemplateRevision();
      setTemplateStatus(result.message);
      setAuditRows(appendAuditLog({ actor: '관리자', action: '서식 개정 확인', target: result.source, metadata: result }));
    }, '서식 개정 여부를 확인하고 있습니다');
  };
  // ai-api(FastAPI) 서버가 실제로 떠 있고 프론트에서 호출 가능한지 확인하는 실제 네트워크 요청입니다.
  const runAiApiHealthCheck = async () => {
    await runWithLoading(async () => {
      try {
        await checkAiApiHealth();
        setAiApiStatus({ tone: 'success', label: '연결됨' });
      } catch (error) {
        setAiApiStatus({ tone: 'danger', label: error.message });
      }
    }, 'AI API 서버 연결을 확인하고 있습니다');
  };
  const runCoreApiHealthCheck = async () => {
    await runWithLoading(async () => {
      try {
        const result = await checkCoreApiStatus();
        setCoreApiStatus({
          tone: 'success',
          label: '연결됨',
          users: result.userCount,
          consultations: result.consultationCount,
        });
      } catch (error) {
        setCoreApiStatus({ tone: 'danger', label: error.message, users: 0, consultations: 0 });
      }
    }, 'Core API 서버 연결을 확인하고 있습니다');
  };
  const formatAuditDetail = (row) => {
    const metadata = row.metadata || {};
    if (metadata.before || metadata.after) return `${metadata.before || '-'} → ${metadata.after || '-'}`;
    if (metadata.reason) return `사유: ${metadata.reason}`;
    if (metadata.title || metadata.type) return [metadata.title, metadata.type].filter(Boolean).join(' · ');
    if (metadata.caseType || metadata.eligibility) return [metadata.caseType, metadata.eligibility].filter(Boolean).join(' · ');
    if (metadata.emailChanged || metadata.organizationChanged || metadata.passwordChanged) {
      return [
        metadata.emailChanged ? `이메일: ${metadata.emailBefore || '-'} → ${metadata.emailAfter || '-'}` : '',
        metadata.organizationChanged ? `소속: ${metadata.organizationBefore || '-'} → ${metadata.organizationAfter || '-'}` : '',
        metadata.passwordChanged ? '비밀번호 변경' : '',
      ].filter(Boolean).join(' / ');
    }
    if (metadata.name || metadata.email || metadata.role) return [metadata.name, metadata.email, metadata.role].filter(Boolean).join(' · ');
    if (metadata.message) return metadata.message;
    return '-';
  };

  return (
    <main className="workspacePage">
      <section className="workflowPanel">
        <h2>운영 관리</h2>
        <div className="workflowColumns">
          <div>
            <h3>감사 로그</h3>
            <div className="adminTableScroll">
              <table className="dataTable auditTable">
                <thead><tr><th>일시</th><th>주체</th><th>작업</th><th>대상</th><th>상세</th></tr></thead>
                <tbody>
                  {auditRows.map((row) => <tr key={`${row.action}-${row.target}-${row.id}`}><td>{row.createdAt || today}</td><td>{row.actor}</td><td>{row.action}</td><td>{row.target}</td><td>{formatAuditDetail(row)}</td></tr>)}
                  <EmptyRows count={Math.max(0, 4 - auditRows.length)} columns={5} />
                </tbody>
              </table>
            </div>
          </div>
          <div>
            <h3>서식 개정 모니터링</h3>
            <div className="resultCard">
              <p>Helplaw24 서식 개정 여부를 점검하는 운영 기능입니다.</p>
              <strong>상태: {templateStatus}</strong>
            </div>
            <button className="primaryButton" type="button" onClick={runTemplateCheck}>서식 개정 확인</button>
            <h3>AI API 서버 연결 상태</h3>
            <div className="resultCard">
              <p>backend/ai-api(FastAPI) 서버가 프론트에서 실제로 호출 가능한 상태인지 확인합니다.</p>
              <strong>
                상태: <span className={`statusChip tone-${aiApiStatus.tone}`}>{aiApiStatus.label}</span>
              </strong>
            </div>
            <button className="primaryButton" type="button" onClick={runAiApiHealthCheck}>연결 확인</button>
            <h3>Core API 서버 연결 상태</h3>
            <div className="resultCard apiStatusCard">
              <p>backend/core-api(Spring Boot) 상담·사용자 API가 프론트에서 호출 가능한지 확인합니다.</p>
              <strong>
                상태: <span className={`statusChip tone-${coreApiStatus.tone}`}>{coreApiStatus.label}</span>
              </strong>
              {coreApiStatus.tone === 'success' ? (
                <div className="apiMetricGrid">
                  <span>사용자 {coreApiStatus.users}명</span>
                  <span>상담 {coreApiStatus.consultations}건</span>
                </div>
              ) : null}
            </div>
            <button className="primaryButton" type="button" onClick={runCoreApiHealthCheck}>백엔드 연결 확인</button>
          </div>
        </div>
      </section>
    </main>
  );
}

function BarChartMock({ consultations }) {
  // 소분류(29개)가 아니라 대분류(친족/상속/가사소송/가족관계등록) 4개 기준으로 집계해 한눈에 보이게 합니다.
  const categoryKeys = caseCategories.map((category) => category.key);
  const countByCategory = (key) => consultations.filter((item) => (item.category || getCaseCategory(item.type)) === key).length;
  const rawMax = Math.max(0, ...categoryKeys.map(countByCategory));
  const scaleMax = computeNiceScaleMax(rawMax);
  return <section className="chartPanel"><h2>사건 유형별 상담 통계</h2><div className="barChart">{categoryKeys.map((key) => { const count = countByCategory(key); const isZero = count === 0; return <div className="barRow" key={key}><span>{key}</span><i className={isZero ? 'zero' : ''} style={{ width: isZero ? 0 : `${Math.max(8, (count / scaleMax) * 100)}%` }}>{count}</i></div>; })}</div></section>;
}

// 도넛의 각 구간(stroke-dasharray/offset)을 계산하는 저수준 기하 로직입니다.
// pathLength="100"으로 원 둘레를 정규화해두면 퍼센트를 그대로 대시 길이로 쓸 수 있습니다.
function buildDonutArcs(visibleSegments, total, gapPercent) {
  let cumulativePercent = 0;
  return visibleSegments.map((segment) => {
    const percent = total ? (segment.value / total) * 100 : 0;
    const trimmedPercent = Math.max(0, percent - gapPercent);
    const dashOffset = 100 - cumulativePercent;
    cumulativePercent += percent;
    return { key: segment.key, className: segment.toneClass, dashArray: `${trimmedPercent} ${100 - trimmedPercent}`, dashOffset };
  });
}

function DonutChart({ total, segments }) {
  const visibleSegments = segments.filter((segment) => segment.value > 0);
  const arcs = buildDonutArcs(visibleSegments, total, visibleSegments.length > 1 ? 2.4 : 0);
  const summary = segments.map((segment) => `${segment.label} ${segment.value}건`).join(', ');
  return (
    <div className="donutChart" role="img" aria-label={`전체 ${total}건 중 ${summary}`}>
      <svg viewBox="0 0 100 100" aria-hidden="true">
        <circle className="donutTrack" cx="50" cy="50" r="40" pathLength="100" />
        {arcs.map((arc) => (
          <circle key={arc.key} className={`donutArc ${arc.className}`} cx="50" cy="50" r="40" pathLength="100" strokeDasharray={arc.dashArray} strokeDashoffset={arc.dashOffset} />
        ))}
      </svg>
      <div className="donutCenter">
        <strong>{total}<em>건</em></strong>
      </div>
    </div>
  );
}

function DonutChartMock({ reviews }) {
  const total = reviews.length;
  const approved = reviews.filter((item) => item.status === '승인').length;
  const rejected = reviews.filter((item) => item.status === '반려').length;
  const pending = Math.max(0, total - approved - rejected);
  // 승인/반려/대기 색상은 나머지 화면의 처리 단계 톤(tone-success/danger/warn)과 그대로 맞춰 일관성을 유지합니다.
  const segments = [
    { key: 'approved', label: '승인', value: approved, toneClass: 'tone-success' },
    { key: 'rejected', label: '반려', value: rejected, toneClass: 'tone-danger' },
    { key: 'pending', label: '대기', value: pending, toneClass: 'tone-warn' },
  ];
  return (
    <section className="chartPanel">
      <h2>분석 처리 현황</h2>
      <div className="donutWrap">
        <DonutChart total={total} segments={segments} />
        <ul className="legendList">
          <li className="legendTotalRow">전체 <strong>{total}건</strong> 접수</li>
          {segments.map((segment) => (
            <li className="legendRow" key={segment.key}>
              <span className={`legendDot ${segment.toneClass}`} />
              <span className="legendLabel">{segment.label}</span>
              <span className="legendValue">{segment.value}건</span>
              <span className="legendPercent">{total ? Math.round((segment.value / total) * 100) : 0}%</span>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}

export { CounselorDashboard, LawyerDashboard, AdminDashboard };
