import React, { useEffect } from 'react';
import { Mic, Check } from 'lucide-react';
import { useInPersonRecording, MIC_STT_WS_URL } from '../../../hooks/useInPersonRecording.js';
import { RealtimeMemoCard } from './RealtimeAnalysisPanel.jsx';

// RealtimeCallControl과 같은 위치·패턴이지만 통화 대신 녹음을 시작/종료합니다.
// 통화 경과 시간 카운트 같은 통화 전용 로직은 옮기지 않고, 녹음 상태(status)는 useInPersonRecording에서
// 온 값을 그대로 씁니다.
export function InPersonRecordingControl({ hasCase, status, onStart, onStop }) {
  const isActive = status === 'connecting' || status === 'recording';
  const sttChip = status === 'recording'
    ? { tone: 'tone-success', label: '녹음 중 · 메모로 기록' }
    : status === 'connecting'
      ? { tone: 'tone-info', label: '녹음 서버 연결 중' }
      : status === 'processing'
        ? { tone: 'tone-info', label: 'STT 처리 중' }
        : status === 'done'
          ? { tone: 'tone-success', label: '녹음 완료' }
          : status === 'error'
            ? { tone: 'tone-warn', label: '녹음 오류' }
            : { tone: 'tone-muted', label: '녹음 대기 중' };
  return (
    <div className="realtimeStatusChips">
      {isActive ? (
        <button type="button" className="callControlButton end" onClick={onStop}>
          <Mic size={14} strokeWidth={2.4} /> 녹음 종료
        </button>
      ) : (
        <button type="button" className="callControlButton start" onClick={onStart} disabled={!hasCase || status === 'processing'}>
          <Mic size={14} strokeWidth={2.4} /> 녹음 시작
        </button>
      )}
      <span className={`statusChip ${sttChip.tone}`}><Mic size={13} strokeWidth={2.4} /> {sttChip.label}</span>
      <span className={`statusChip ${hasCase ? 'tone-info' : 'tone-muted'}`}><Check size={13} strokeWidth={2.4} /> 메모 · {hasCase ? '입력 가능' : '사건 선택 필요'}</span>
    </div>
  );
}

// mic-stt(ai_judge/validation/confidence)는 참고용일 뿐입니다. 소득기준·소멸시효 등을 계산하는
// Rule Engine 독점 원칙과는 별개 경로이므로, 이 값은 analysis state에 절대 병합하지 않고
// sttResult로만 화면에 노출합니다.
export function InPersonSttReferenceBadge({ sttResult }) {
  const aiJudge = sttResult?.ai_judge;
  const validation = sttResult?.validation;
  if (!aiJudge || !validation) return null;

  const filteredFlags = (validation.flags || [])
    .filter((f) => f !== 'recommend_inperson_consultation');

  return (
    <div className="resultCard sttReferenceCard">
      <span className="statusChip tone-muted">참고용 · 최종판단 아님</span>
      <p className="reasonText">
        STT 자체 추정: {validation.case_type_final ?? '미판단'}
        {aiJudge.support_level ? ` · 지원 ${aiJudge.support_level}` : ''}
      </p>
      {filteredFlags.length > 0 && (
        <ul className="sttFlagList">
          {filteredFlags.map((f) => (
            <li key={f} className="statusChip tone-warn">{f}</li>
          ))}
        </ul>
      )}
    </div>
  );
}

// RealtimeAnalysisPanel(전화상담)을 참고해 구조를 복제하되, 통화 시작/종료 대신 녹음 시작/종료를 씁니다.
// segments는 idx 순으로 이어붙여 일반 텍스트로 만든 뒤 onUpdateConsultation으로 전달합니다 — 전화상담의
// 메모 입력과 동일한 경로이며, consult/analyze 파이프라인은 이 변경으로 영향을 받지 않습니다.
export function InPersonAnalysisPanel({ selectedCase, onUpdateConsultation, caseMeta }) {
  const hasCase = Boolean(selectedCase);
  const { status, sttResult, errorMessage, startRecording, stopRecording } =
    useInPersonRecording({ wsUrl: MIC_STT_WS_URL });

  useEffect(() => {
    if (status === 'done' && sttResult?.segments?.length) {
      const transcriptText = [...sttResult.segments]
        .sort((a, b) => a.idx - b.idx)
        .map((s) => s.text)
        .join(' ');
      onUpdateConsultation(selectedCase.id, { memo: transcriptText });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [status, sttResult]);

  const headline = status === 'recording'
    ? '녹음 중입니다. 대면 상담 내용이 실시간으로 전송됩니다.'
    : status === 'processing'
      ? '녹음을 마쳤습니다. STT 결과를 기다리는 중입니다.'
      : status === 'error'
        ? (errorMessage || '녹음 처리 중 오류가 발생했습니다.')
        : '대면 상담을 시작하려면 위 ‘녹음 시작’을 눌러 진행하세요.';

  return (
    <section className="realtimeWorkbenchPanel" aria-label="대면 상담 메모">
      <div className="realtimeWorkbenchHeader">
        <div>
          <span className="flowStageEyebrow">대면 상담</span>
          <strong>{headline}</strong>
          <p>마이크 녹음 종료 시 대화 내용이 자동으로 상담 메모에 반영됩니다.</p>
        </div>
        <InPersonRecordingControl
          hasCase={hasCase}
          status={status}
          onStart={startRecording}
          onStop={stopRecording}
        />
      </div>
      <div className="realtimeConsultationLayout">
        <div className="realtimeConsultationMain">
          <RealtimeMemoCard selectedCase={selectedCase} onUpdateConsultation={onUpdateConsultation} />
          <InPersonSttReferenceBadge sttResult={sttResult} />
        </div>
        <aside className="realtimeConsultationSide">
          {caseMeta}
        </aside>
      </div>
    </section>
  );
}
