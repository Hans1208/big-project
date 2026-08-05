import React, { useEffect, useRef, useState } from 'react';
import { Mic, Check, EyeOff, Headphones, Radio } from 'lucide-react';
import { RealtimeMemoCard } from './RealtimeAnalysisPanel.jsx';
import { CollapsibleSection } from '../../../components/common.jsx';

// RealtimeCallControl과 같은 위치·패턴이지만 통화 대신 녹음을 시작/종료합니다.
// 통화 경과 시간 카운트 같은 통화 전용 로직은 옮기지 않고, 녹음 상태(status)는 useInPersonRecording에서
// 온 값을 그대로 씁니다.
export function InPersonRecordingControl({ hasCase, status, onStart, onStop }) {
  const isActive = status === 'connecting' || status === 'recording';
  const sttChip = status === 'recording'
    ? { tone: 'tone-success', label: '녹음 중 · 개인정보 자동 마스킹' }
    : status === 'connecting'
      ? { tone: 'tone-info', label: '녹음 서버 연결 중' }
      : status === 'processing'
        ? { tone: 'tone-info', label: 'STT·마스킹 처리 중' }
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

// stt-mask-api는 화자분리(speaker) 정보를 주지 않아 지금은 이 분기를 안 탑니다. 다만 요구사항이
// "화자분리가 가능하면 화자별로, 아니면 그냥 텍스트대로"라서, segment에 speaker 필드가 실제로
// 실리는 날 코드 변경 없이 바로 화자별로 나뉘어 쌓이도록 미리 대응해 둡니다.
function buildTranscriptChunk(segments, field) {
  const hasSpeaker = segments.some((segment) => segment.speaker);
  return segments
    .map((segment) => {
      if (segment.error) return '[변환 실패]';
      const value = segment[field] || '';
      return hasSpeaker && segment.speaker ? `[${segment.speaker}] ${value}` : value;
    })
    .filter(Boolean)
    .join(hasSpeaker ? '\n' : ' ')
    .trim();
}

function buildTranscript(segments, field) {
  return buildTranscriptChunk([...segments].sort((a, b) => a.idx - b.idx), field);
}

// "녹음 시작"을 다시 눌렀는데 이전 세션 텍스트가 실시간 상담 메모에 이미 쌓여 있으면, 그걸 그냥
// 이어붙이면 이전 상담 내용과 새 상담 내용이 뒤섞입니다. 그렇다고 묻지도 않고 지우면 실수로
// 다시 누른 경우 되돌릴 수 없이 날아갑니다 — 그래서 확인 팝업을 거칩니다.
function RestartRecordingConfirmModal({ onConfirm, onCancel }) {
  return (
    <div className="modalBackdrop" role="presentation">
      <div className="modal">
        <div className="modalHeader"><h2>녹음 재시작</h2></div>
        <p>녹음을 재시작하면 기존 녹음자료들이 사라집니다.</p>
        <div className="restartConfirmActions">
          <button className="restartConfirmButton" type="button" onClick={onCancel}>아니오</button>
          <button className="restartConfirmButton" type="button" onClick={onConfirm}>네</button>
        </div>
      </div>
    </div>
  );
}

// core-api(InPersonRecordingWebSocketHandler)가 stt-mask-api로 실제 마스킹한 결과를 원문/마스킹본
// 토글로 보여줍니다. AnalysisWorkbench의 "개인정보는 자동으로 가려집니다" 카드와 같은 UX입니다.
// 기본값을 마스킹본으로 두는 이유도 동일합니다 — 원문은 검증이 필요할 때만 확인합니다.
export function InPersonSttPreview({ segments }) {
  const [showMasked, setShowMasked] = useState(true);
  if (!segments.length) return null;
  const hasError = segments.some((segment) => segment.error);
  const text = buildTranscript(segments, showMasked ? 'maskedText' : 'text');
  return (
    <CollapsibleSection icon={EyeOff} title="개인정보 마스크 결과">
      <div className="resultCard sttReferenceCard">
        <div className="segmented compactSegmented">
          <button type="button" className={showMasked ? 'active' : ''} onClick={() => setShowMasked(true)}>개인정보 가림</button>
          <button type="button" className={!showMasked ? 'active' : ''} onClick={() => setShowMasked(false)}>원문</button>
        </div>
        {!showMasked ? <p className="sensitiveSourceNotice">민감정보 포함 가능 · 검증 시에만 확인</p> : null}
        <p className="sttPreviewText">{text || '녹음 결과가 없습니다.'}</p>
        {hasError ? <p className="helperText">일부 구간은 변환에 실패해 메모에서 제외되었습니다.</p> : null}
      </div>
    </CollapsibleSection>
  );
}

// RealtimeAnalysisPanel(전화상담)을 참고해 구조를 복제하되, 통화 시작/종료 대신 녹음 시작/종료를 씁니다.
//
// 전화상담과 결과가 섞여 보이지 않도록 memo/memoMasked가 아니라 별도 필드
// (inpersonMemo/inpersonMemoMasked)에 씁니다 — RealtimeMemoCard의 field prop으로 지정합니다.
//
// segment_result가 올 때마다(녹음 종료를 기다리지 않고) "실시간 상담 메모" 칸에 바로 반영합니다.
// 다만 전체를 통째로 다시 쓰면 그 사이 상담원이 직접 입력한 메모(같은 칸의 "메모 추가")를
// 덮어써 버리므로, 이미 반영한 segment 개수(flushedCountRef)를 추적해 "새로 도착한 조각만"
// 기존 값 뒤에 이어붙입니다.
//
// status/segments/startRecording/stopRecording은 useInPersonRecording을 여기서 직접 부르지 않고
// AnalysisWorkbench로부터 props로 받습니다 — "상담 저장" 버튼이 녹음 상태(상담 중/변환 중)에
// 따라 라벨을 바꿔야 해서, 그 버튼이 있는 AnalysisWorkbench가 이 훅을 대신 소유합니다.
export function InPersonAnalysisPanel({
  selectedCase, onUpdateConsultation,
  inPersonStatus: status, inPersonSegments: segments, inPersonErrorMessage: errorMessage,
  onStartInPersonRecording, onStopInPersonRecording,
}) {
  const hasCase = Boolean(selectedCase);

  const [pendingRestartConfirm, setPendingRestartConfirm] = useState(false);
  const hasExistingMemo = Boolean((selectedCase?.inpersonMemo || '').trim() || (selectedCase?.inpersonMemoMasked || '').trim());
  const handleStartClick = () => {
    if (hasExistingMemo) {
      setPendingRestartConfirm(true);
      return;
    }
    onStartInPersonRecording();
  };
  const confirmRestart = () => {
    setPendingRestartConfirm(false);
    onUpdateConsultation(selectedCase.id, { inpersonMemo: '', inpersonMemoMasked: '' });
    onStartInPersonRecording();
  };

  const flushedCountRef = useRef(0);
  useEffect(() => {
    // 새 녹음 세션 시작(연결 중으로 전환) — 다음 세션의 segments는 처음부터 다시 세야 합니다.
    if (status === 'connecting') {
      flushedCountRef.current = 0;
    }
  }, [status]);

  useEffect(() => {
    if (!hasCase || segments.length <= flushedCountRef.current) return;
    const sorted = [...segments].sort((a, b) => a.idx - b.idx);
    const newSegments = sorted.slice(flushedCountRef.current);
    flushedCountRef.current = sorted.length;

    const newText = buildTranscriptChunk(newSegments, 'text');
    const newMaskedText = buildTranscriptChunk(newSegments, 'maskedText');
    if (!newText && !newMaskedText) return;

    const currentMemo = selectedCase.inpersonMemo || '';
    const currentMasked = selectedCase.inpersonMemoMasked || '';
    onUpdateConsultation(selectedCase.id, {
      inpersonMemo: newText ? (currentMemo ? `${currentMemo} ${newText}` : newText) : currentMemo,
      inpersonMemoMasked: newMaskedText ? (currentMasked ? `${currentMasked} ${newMaskedText}` : newMaskedText) : currentMasked,
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [segments, hasCase]);

  const headline = status === 'recording'
    ? '녹음 중입니다. 대면 상담 내용이 실시간으로 전송됩니다.'
    : status === 'processing'
      ? '녹음을 마쳤습니다. STT·마스킹 결과를 기다리는 중입니다.'
      : status === 'error'
        ? (errorMessage || '녹음 처리 중 오류가 발생했습니다.')
        : '대면 상담을 시작하려면 위 ‘녹음 시작’을 눌러 진행하세요.';

  return (
    <section className="realtimeWorkbenchPanel" aria-label="대면 상담 메모">
      <div className="realtimeWorkbenchHeader">
        <div className="realtimeHeaderTags">
          <span className="roleIdentityBadge roleIdentityBadge-counselor"><Headphones size={12} strokeWidth={2.4} aria-hidden="true" /> 상담원 업무</span>
          <span className="flowStageEyebrow"><Radio size={13} strokeWidth={2.4} aria-hidden="true" /> 실시간 상담</span>
        </div>
      </div>
      <div className="realtimeConsultationLayout">
        <div className="realtimeConsultationMain">
          <div className="realtimeSplitRow">
            <div className="realtimeSplitColumn">
              <strong>{headline}</strong>
              <p>마이크 녹음 중 개인정보가 가려진 대화 내용이 실시간으로 상담 메모에 반영됩니다.</p>
              <InPersonRecordingControl
                hasCase={hasCase}
                status={status}
                onStart={handleStartClick}
                onStop={onStopInPersonRecording}
              />
              {/* "개인정보 가림"/"원문" 토글은 녹음 종료 후 결과만 보여달라는 요구에 맞춰
                  status === 'done'일 때만 렌더링합니다(위 실시간 메모와는 별개 요구사항). */}
              {status === 'done' ? <InPersonSttPreview segments={segments} /> : null}
            </div>
            <RealtimeMemoCard
              selectedCase={selectedCase}
              onUpdateConsultation={onUpdateConsultation}
              field="inpersonMemo"
              composerPlaceholder="대면 상담 내용을 바로 적어주세요."
            />
          </div>
        </div>
      </div>
      {pendingRestartConfirm ? (
        <RestartRecordingConfirmModal
          onConfirm={confirmRestart}
          onCancel={() => setPendingRestartConfirm(false)}
        />
      ) : null}
    </section>
  );
}
