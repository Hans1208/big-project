import React, { useEffect, useRef, useState } from 'react';
import { Mic, Check } from 'lucide-react';
import { useInPersonRecording } from '../../../hooks/useInPersonRecording.js';
import { RealtimeMemoCard } from './RealtimeAnalysisPanel.jsx';
import { correctClientName } from '../shared/nameCorrection.js';

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
export function InPersonSttPreview({ segments, clientName }) {
  const [showMasked, setShowMasked] = useState(true);
  if (!segments.length) return null;
  const hasError = segments.some((segment) => segment.error);
  const text = correctClientName(buildTranscript(segments, showMasked ? 'maskedText' : 'text'), clientName);
  return (
    <div className="resultCard sttReferenceCard">
      <div className="segmented compactSegmented">
        <button type="button" className={showMasked ? 'active' : ''} onClick={() => setShowMasked(true)}>개인정보 가림</button>
        <button type="button" className={!showMasked ? 'active' : ''} onClick={() => setShowMasked(false)}>원문</button>
      </div>
      {!showMasked ? <p className="sensitiveSourceNotice">민감정보 포함 가능 · 검증 시에만 확인</p> : null}
      <p className="sttPreviewText">{text || '녹음 결과가 없습니다.'}</p>
      {hasError ? <p className="helperText">일부 구간은 변환에 실패해 메모에서 제외되었습니다.</p> : null}
    </div>
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
export function InPersonAnalysisPanel({ selectedCase, onUpdateConsultation, caseMeta }) {
  const hasCase = Boolean(selectedCase);
  const { status, segments, errorMessage, startRecording, stopRecording } =
    useInPersonRecording({ consultationId: selectedCase?.coreId });

  const [pendingRestartConfirm, setPendingRestartConfirm] = useState(false);
  const hasExistingMemo = Boolean((selectedCase?.inpersonMemo || '').trim() || (selectedCase?.inpersonMemoMasked || '').trim());
  const handleStartClick = () => {
    if (hasExistingMemo) {
      setPendingRestartConfirm(true);
      return;
    }
    startRecording();
  };
  const confirmRestart = () => {
    setPendingRestartConfirm(false);
    onUpdateConsultation(selectedCase.id, { inpersonMemo: '', inpersonMemoMasked: '' });
    startRecording();
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

    // 상담원이 이름칸에 적어둔 이름이 있으면, 받아쓰기가 잘못 들은 이름을 그 이름으로 되돌립니다.
    // 이 메모가 그대로 상담 저장 -> AI 분석 -> 서식 초안까지 흘러가기 때문에, 여기서 안 고치면
    // 청구인 이름이 틀린 채로 법률 문서가 만들어집니다.
    const clientName = selectedCase.name || '';
    const newText = correctClientName(buildTranscriptChunk(newSegments, 'text'), clientName);
    const newMaskedText = correctClientName(buildTranscriptChunk(newSegments, 'maskedText'), clientName);
    if (!newText && !newMaskedText) return;

    const currentMemo = selectedCase.inpersonMemo || '';
    const currentMasked = selectedCase.inpersonMemoMasked || '';
    onUpdateConsultation(selectedCase.id, {
      inpersonMemo: newText ? (currentMemo ? `${currentMemo} ${newText}` : newText) : currentMemo,
      inpersonMemoMasked: newMaskedText ? (currentMasked ? `${currentMasked} ${newMaskedText}` : newMaskedText) : currentMasked,
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [segments, hasCase]);

  // 실제 흐름은 "녹음 -> 받아쓰기에서 이름이 틀린 걸 발견 -> 이름칸을 고침" 순서입니다. 그래서
  // 새로 들어오는 조각만 고쳐서는 부족하고, 이름이 바뀐 시점에 이미 쌓여 있는 메모까지 같이
  // 고쳐야 저장되는 본문에서 틀린 이름이 사라집니다.
  //
  // 고칠 게 없으면 아무것도 안 하므로(아래 비교) 갱신이 반복되지 않습니다.
  //
  // 이름칸이 바로 옆(caseMeta)에 있어서 한 글자 칠 때마다 이 효과가 돕니다. 메모를 덮어쓰는
  // 일이라 '문', '문가'처럼 아직 다 안 친 상태로 반영되면 안 되므로, 타이핑이 멎은 뒤에만
  // 한 번 적용합니다.
  useEffect(() => {
    if (!hasCase) return undefined;
    const timer = setTimeout(() => {
      const clientName = selectedCase.name || '';
      const memo = selectedCase.inpersonMemo || '';
      const masked = selectedCase.inpersonMemoMasked || '';
      const nextMemo = correctClientName(memo, clientName);
      const nextMasked = correctClientName(masked, clientName);
      if (nextMemo === memo && nextMasked === masked) return;
      onUpdateConsultation(selectedCase.id, { inpersonMemo: nextMemo, inpersonMemoMasked: nextMasked });
    }, 800);
    return () => clearTimeout(timer);
    // 메모 내용은 의존성에서 뺍니다. 상담원이 메모를 직접 고칠 수 있게 되면서
    // (RealtimeMemoCard), 메모가 바뀔 때마다 이 교정이 돌면 일부러 적은 이름까지
    // 되돌려 버립니다 — 예를 들어 상대방 이름이 내담자와 소리가 비슷하면, 적는 족족
    // 내담자 이름으로 바뀝니다. 사람이 고친 것이 기계보다 우선입니다.
    // 이름칸이 바뀐 순간에만 한 번 훑습니다.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedCase?.id, selectedCase?.name]);

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
        <div>
          <span className="flowStageEyebrow">대면 상담</span>
          <strong>{headline}</strong>
          <p>마이크 녹음 중 개인정보가 가려진 대화 내용이 실시간으로 상담 메모에 반영됩니다.</p>
        </div>
        <InPersonRecordingControl
          hasCase={hasCase}
          status={status}
          onStart={handleStartClick}
          onStop={stopRecording}
        />
      </div>
      <div className="realtimeConsultationLayout">
        <div className="realtimeConsultationMain">
          <RealtimeMemoCard
            selectedCase={selectedCase}
            onUpdateConsultation={onUpdateConsultation}
            field="inpersonMemo"
            composerPlaceholder="대면 상담 내용을 바로 적어주세요."
          />
          {/* "개인정보 가림"/"원문" 토글은 녹음 종료 후 결과만 보여달라는 요구에 맞춰
              status === 'done'일 때만 렌더링합니다(위 실시간 메모와는 별개 요구사항). */}
          {status === 'done' ? <InPersonSttPreview segments={segments} clientName={selectedCase?.name || ''} /> : null}
        </div>
        <aside className="realtimeConsultationSide">
          {caseMeta}
        </aside>
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
