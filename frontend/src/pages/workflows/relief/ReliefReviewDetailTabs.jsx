import React, { useState } from 'react';
import { ShieldCheck, TrendingUp, Gavel, Award } from 'lucide-react';
import { InlineEmptyNotice } from '../../../components/common.jsx';
import { criterionLabel, mentionLabel, evidenceStatusTone } from '../shared/reviewHelpers.js';

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
export function ReliefReviewDetailTabs({ detail }) {
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
