import React, { useState } from 'react';
import { PhoneCall, Check, Mic, Clock, Info, Sparkles, MessageSquareText, Headphones, Radio } from 'lucide-react';
import { buildSuggestedQuestions, formatCallDuration } from '../shared/formatters.js';
import { CallLiveIndicator } from '../components/CallLiveIndicator.jsx';
import { CallAudioVisualizer } from '../components/CallAudioVisualizer.jsx';

export function RealtimeCallControl({
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
          <button type="button" className="callControlButton start" onClick={onStartCall} disabled={!hasCase || isLoadingAudioCalls || !availableAudioCalls.some((call) => call.callId === selectedAudioCallId)}>
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

// 통화 중 곧바로 타이핑할 수 있는 실제 입력창입니다. 여기 적은 내용이 selectedCase[field]로 저장되고,
// 아래 'AI 분석 결과'가 그대로 이 텍스트를 분석 대상으로 씁니다 — 즉 이 칸을 채우는 것이
// 실시간 분석을 정확하게 만드는 가장 중요한 행동입니다.
//
// field: 전화상담과 대면상담이 같은 상담(case)의 서로 다른 필드에 각자 기록해야 해서
// (전화상담과 대면상담 결과가 섞여 보이면 안 된다는 요구) 대상 필드를 파라미터로 받습니다.
// 기본값 'memo'는 전화상담(RealtimeAnalysisPanel) 쪽 기존 동작 그대로입니다.
export function RealtimeMemoCard({ selectedCase, onUpdateConsultation, field = 'memo', composerPlaceholder = '통화 내용을 바로 적어주세요.' }) {
  const hasCase = Boolean(selectedCase);
  const memo = selectedCase?.[field] || '';
  const charCount = memo.trim().length;
  const [pendingMemo, setPendingMemo] = useState('');
  const addMemo = () => {
    const nextLine = pendingMemo.trim();
    if (!hasCase || !nextLine) return;
    onUpdateConsultation(selectedCase.id, { [field]: memo ? `${memo}\n${nextLine}` : nextLine });
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
          placeholder={composerPlaceholder}
        />
        <button type="button" className="callAnalyzeButton" onClick={addMemo} disabled={!hasCase || !pendingMemo.trim()}>메모 추가</button>
      </div>
      <p className="helperText">AI 분석 기준 메모</p>
    </article>
  );
}
export function RealtimeSuggestedQuestions({ memoText }) {
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
export function LiveCaptionCard({ callStatus, audioStatus, captions }) {
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

export function RealtimeAnalysisPanel({ selectedCase, onUpdateConsultation, callStatus, callSeconds, audioStatus, liveCaptions, availableAudioCalls, selectedAudioCallId, isLoadingAudioCalls, onSelectAudioCall, onRefreshAudioCalls, onStartCall, onEndCall, audioStreamRef }) {
  const hasCase = Boolean(selectedCase);
  const headline = callStatus === 'ongoing'
    ? '통화 중입니다. 들은 내용을 바로 적으면서 진행하세요.'
    : callStatus === 'ended'
      ? '통화를 마쳤습니다. 메모를 다듬은 뒤 분석을 시작하세요.'
      : '전화를 받으면 위 ‘통화 시작’을 눌러 진행하세요.';
  return (
    <section className="realtimeWorkbenchPanel roleAccent-counselor" aria-label="실시간 상담 메모">
      <div className="realtimeWorkbenchHeader">
        <div className="realtimeHeaderTags">
          <span className="roleIdentityBadge roleIdentityBadge-counselor"><Headphones size={12} strokeWidth={2.4} aria-hidden="true" /> 상담원 업무</span>
          <span className="flowStageEyebrow"><Radio size={13} strokeWidth={2.4} aria-hidden="true" /> 실시간 상담</span>
        </div>
      </div>
      <div className="realtimeConsultationLayout">
        <div className="realtimeConsultationMain">
          {callStatus === 'ongoing' && audioStreamRef ? (
            <CallAudioVisualizer audioStreamRef={audioStreamRef} active={audioStatus === 'streaming'} />
          ) : null}
          <LiveCaptionCard callStatus={callStatus} audioStatus={audioStatus} captions={liveCaptions} />
          <div className="realtimeSplitRow">
            <div className="realtimeSplitColumn">
              <strong>{headline}</strong>
              <p>통화 내용 자동 받아쓰기를 준비 중입니다. 현재는 메모를 기준으로 분석합니다.</p>
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
              {hasCase ? <RealtimeSuggestedQuestions memoText={selectedCase?.memo || ''} /> : null}
            </div>
            <RealtimeMemoCard selectedCase={selectedCase} onUpdateConsultation={onUpdateConsultation} />
          </div>
        </div>
      </div>
    </section>
  );
}
