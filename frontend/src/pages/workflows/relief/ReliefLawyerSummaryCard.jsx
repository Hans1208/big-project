import React from 'react';
import { Info } from 'lucide-react';
import { parseLawyerSummary } from '../shared/reviewHelpers.js';

// requires_lawyer_review + checklist_summary_for_lawyer 전용 카드입니다. ReliefReviewDetailTabs(4탭)의
// 근거 상세와는 성격이 달라 별도 카드로 분리합니다 — 이쪽은 변호사에게 바로 넘길 수 있는 한 줄 요약이고,
// 탭 쪽은 상담원이 각 신호의 근거를 하나씩 파고들 때 보는 상세 화면입니다.
export function ReliefLawyerSummaryCard({ detail }) {
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
