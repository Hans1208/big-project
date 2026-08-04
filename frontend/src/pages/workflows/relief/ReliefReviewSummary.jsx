import React from 'react';

// ── 아래는 dashboards.jsx(변호사 대시보드의 서식 초안 검토 대기 패널·HITL 모달)가 그대로 가져다 쓰는
// 표시 전용 헬퍼입니다. DraftWorkbench 내부 로직과는 독립적이라, 이 파일의 다른 부분과 상관없이
// 안전하게 export만 유지합니다. ──

// /consult/analyze가 돌려준 구조검토 체크리스트입니다.
// 승소·집행·타당성은 결론이 아니라 '신호'이므로, 판정처럼 보이지 않게 근거 문장 그대로만 둡니다.
export function ReliefReviewSummary({ review }) {
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
