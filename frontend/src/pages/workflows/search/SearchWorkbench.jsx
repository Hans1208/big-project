import React, { useState } from 'react';
import { ClipboardList, CheckCircle2, Gavel, BookOpen } from 'lucide-react';
import { WorkPageHeader, InlineEmptyNotice } from '../../../components/common.jsx';
import { searchReferenceCandidates } from '../../../services/legalAidApi.js';
import { caseOptions } from '../shared/caseHelpers.js';
import { CasePicker } from '../components/CasePicker.jsx';

export function SearchWorkbench({ consultations }) {
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
