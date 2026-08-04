import React, { useEffect, useRef, useState } from 'react';
import { ClipboardList, CheckCircle2, Gavel, BookOpen } from 'lucide-react';
import { WorkPageHeader, InlineEmptyNotice, friendlyErrorMessage } from '../../../components/common.jsx';
import { searchReferenceCandidates } from '../../../services/legalAidApi.js';
import { recommendStatutes, searchStatutes } from '../../../services/aiApiClient.js';
import { caseOptions } from '../shared/caseHelpers.js';
import { CasePicker } from '../components/CasePicker.jsx';

// 법령 검색을 한 번에 몇 건씩 받아올지. 추천은 상위 몇 건만 의미가 있어 서버가
// 따로 정하고(RECOMMEND_TOP_K), 이 값은 '직접 검색'에만 씁니다.
const STATUTE_PAGE_SIZE = 20;

// 법령 API의 시행일은 '20260317' 형태입니다. 그대로 두면 날짜로 안 읽힙니다.
function formatStatuteDate(value) {
  const digits = String(value || '').replace(/\D/g, '');
  if (digits.length !== 8) return value || '';
  return `${digits.slice(0, 4)}. ${Number(digits.slice(4, 6))}. ${Number(digits.slice(6, 8))}.`;
}

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

  // 법령 탭만 실제 검색에 연결돼 있습니다. 판례·유사 상담사례는 아직 색인이 없어
  // 예시 목록을 그대로 씁니다 — 어느 쪽을 보고 있는지 화면에 밝혀둡니다.
  const [statuteResults, setStatuteResults] = useState([]);
  const [statuteLoading, setStatuteLoading] = useState(false);
  // 전문을 펼쳐 둔 조문. 조문은 항이 여러 개라 접힌 채로는 요건을 확인할 수 없고,
  // 그렇다고 전부 펼쳐두면 목록에서 훑어보며 고를 수가 없습니다.
  const [expandedIds, setExpandedIds] = useState([]);
  // 한 번에 받아올 조문 수. '더 보기'로 늘립니다 — 5건만 보여주면 찾는 조문이
  // 6위였을 때 상담원이 "없다"고 결론내게 됩니다.
  const [statuteTopK, setStatuteTopK] = useState(STATUTE_PAGE_SIZE);
  const [statuteExhausted, setStatuteExhausted] = useState(false);
  const isStatuteTab = referenceType === 'statute';

  const results = isStatuteTab
    ? statuteResults
    : (searched || mode === '추천'
      ? searchReferenceCandidates({ type: referenceType, query, caseType: selectedCase?.analysis?.caseType || selectedCase?.type })
      : []);
  const selectedTitles = selected.map((item) => item.title);

  // 검색 결과 한 건을 화면 카드가 기대하는 모양({id, title, source})으로 맞춥니다.
  // 조문 본문과 유사도는 추가 필드로 얹어, 카드가 쓸 수 있으면 쓰도록 합니다.
  const toReferenceItem = (row) => ({
    id: row.id,
    title: row.title,
    source: row.source || '국가법령정보센터',
    caseType: '공통',
    content: row.content || '',
    similarityPercent: row.similarity_percent ?? null,
    reason: row.reason || '',
    effectiveDate: row.effective_date || '',
  });

  // isCurrent: 응답이 도착했을 때도 이 요청이 여전히 최신인지 묻습니다. 상담을
  // 빠르게 넘기면 앞선 요청이 뒤늦게 도착해 새 상담의 결과를 덮어씁니다.
  const runStatuteQuery = async (kind, topK = STATUTE_PAGE_SIZE, isCurrent = () => true) => {
    setStatuteLoading(true);
    setSearched(true);
    try {
      const payload = kind === '추천'
        ? await recommendStatutes({
          caseType: selectedCase?.analysis?.caseType || selectedCase?.type || '',
          caseSubtype: selectedCase?.analysis?.caseSubtype || '',
          summary: selectedCase?.analysis?.summary || '',
          extractedJson: selectedCase?.analysis?.extractedJson || {},
        })
        : await searchStatutes({ query, topK });
      if (!isCurrent()) return;
      const rows = (payload?.results || []).map(toReferenceItem);
      setStatuteResults(rows);
      setStatuteTopK(topK);
      setExpandedIds([]);   // 결과가 바뀌면 펼쳐둔 상태도 의미가 없습니다.
      // 더 청한 만큼 안 왔으면 색인에 더 없다는 뜻이라 '더 보기'를 감춥니다.
      setStatuteExhausted(kind === '추천' || rows.length < topK);
      setReferenceMessage(rows.length
        ? `조문 ${rows.length}건 · 국가법령정보센터`
        : '해당하는 조문을 찾지 못했습니다 · 검색어를 바꿔보세요');
    } catch (error) {
      if (!isCurrent()) return;
      setStatuteResults([]);
      setReferenceMessage(friendlyErrorMessage(error, '법령을 불러오지 못했습니다'));
    } finally {
      if (isCurrent()) setStatuteLoading(false);
    }
  };

  // 추천은 '지금 고른 상담'에 딸린 결과라, 상담을 바꾸면 곧바로 다시 받아와야
  // 합니다. 예전에는 탭 핸들러에서만 불러서, 상담을 바꿔도 앞 상담의 조문이
  // 그대로 남아 있다가 탭을 왔다 갔다 해야 갱신됐습니다 — 화면에는 새 상담이
  // 떠 있는데 목록은 남의 사건이라 알아채기도 어렵습니다.
  //
  // 호출 지점을 여기 하나로 모읍니다. 상담·자료종류·모드 중 무엇이 바뀌든 조건이
  // 맞으면 다시 부르고, 아니면 남은 결과를 지웁니다.
  const latestRequest = useRef(0);
  useEffect(() => {
    if (!isStatuteTab) {
      setStatuteResults([]);
      return;
    }
    // 직접 검색 모드에서는 상담원이 넣은 검색어가 기준이라 상담을 바꿔도
    // 결과를 건드리지 않습니다. 지우면 방금 찾아둔 조문이 사라집니다.
    if (mode !== '추천') return;
    if (!selectedCase?.analysis?.summary) {
      setStatuteResults([]);
      setReferenceMessage('이 상담은 아직 분석 전입니다 · 실시간 분석을 먼저 실행해 주세요');
      return;
    }
    // 상담을 빠르게 넘기면 앞선 요청이 뒤늦게 도착해 새 상담 화면에 옛 결과를
    // 덮어쓸 수 있습니다. 가장 마지막 요청만 반영합니다.
    const ticket = ++latestRequest.current;
    runStatuteQuery('추천', undefined, () => ticket === latestRequest.current);
    // runStatuteQuery는 매 렌더마다 새로 만들어지므로 의존성에 넣지 않습니다.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [caseId, referenceType, mode]);

  const runAiReferenceSearch = () => {
    if (isStatuteTab) {
      runStatuteQuery('추천');
      return;
    }
    setSearched(true);
    setReferenceMessage('추천 후보 표시 · 판례·유사사례는 아직 예시 목록입니다');
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
                  setStatuteResults([]);
                  setReferenceMessage('');
                }}
              >
                {item.label}
              </button>
            ))}
          </div>
          <div className="segmented referenceModeTabs">
            {['추천', '직접 검색'].map((item) => <button className={mode === item ? 'active' : ''} type="button" key={item} onClick={() => { setMode(item); setSearched(item === '추천'); setStatuteResults([]); setReferenceMessage(''); }}>{item}</button>)}
          </div>
        </div>
        {mode === '직접 검색' ? (
          <div className="referenceSearchBox">
            <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder={`${label} 검색어`} />
            <button type="button" disabled={statuteLoading}
              onClick={() => (isStatuteTab ? runStatuteQuery('직접 검색') : setSearched(true))}>
              {statuteLoading ? '검색 중…' : '검색'}
            </button>
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
                // 예전에는 카드 전체가 button이라 안에 '전문 보기'를 넣을 수 없었습니다
                // (button 안의 button은 유효하지 않은 마크업입니다). 조문은 항이 여러 개라
                // 접힌 상태로는 요건을 확인할 수 없으므로, 카드를 div로 바꾸고 '선택'과
                // '전문 보기'를 각각 버튼으로 둡니다.
                const isOpen = expandedIds.includes(item.id);
                const isClamped = Boolean(item.content) && item.content.split('\n').length > 4;
                return (
                  <div className={isSelected ? 'referenceCard selected' : 'referenceCard'} key={item.id}>
                    <span className="referenceCardTitle"><Gavel size={13} strokeWidth={2.2} aria-hidden="true" /> {item.title}</span>
                    {/* 조문 본문을 함께 보여줍니다. 제목만으로는 이 조문이 사건에 맞는지
                        판단할 수 없어, 상담원이 결국 법령정보센터를 따로 열어야 합니다. */}
                    {item.content ? (
                      <span className={isOpen ? 'referenceCardBody open' : 'referenceCardBody'}>{item.content}</span>
                    ) : null}
                    {isClamped ? (
                      <button className="referenceCardToggle" type="button"
                        onClick={() => setExpandedIds((current) => (isOpen
                          ? current.filter((value) => value !== item.id)
                          : [...current, item.id]))}
                      >
                        {isOpen ? '접기' : '조문 전문 보기'}
                      </button>
                    ) : null}
                    <span className="referenceCardMeta">
                      {item.source}
                      {item.effectiveDate ? ` · 시행 ${formatStatuteDate(item.effectiveDate)}` : ''}
                      {/* 유사도는 순위를 매긴 근거일 뿐 정답률이 아닙니다. 이 조문을
                          쓸지는 상담원·변호사가 정합니다(HITL). */}
                      {item.similarityPercent != null ? ` · 유사도 ${item.similarityPercent}%` : ''}
                      {item.similarityPercent == null && item.caseType ? ` · ${item.caseType}` : ''}
                    </span>
                    {item.reason ? <span className="referenceCardReason">{item.reason}</span> : null}
                    <button className={`statusChip referenceCardPick ${isSelected ? 'tone-success' : 'tone-muted'}`}
                      type="button" onClick={() => adoptReference(item)}
                    >
                      {isSelected ? <CheckCircle2 size={12} strokeWidth={2.4} aria-hidden="true" /> : null} {isSelected ? '선택됨' : '선택'}
                    </button>
                  </div>
                );
              }) : <InlineEmptyNotice>조건 일치 {label} 없음</InlineEmptyNotice>}
              {isStatuteTab && results.length && !statuteExhausted ? (
                <button className="secondaryActionButton referenceMoreButton" type="button"
                  disabled={statuteLoading}
                  onClick={() => runStatuteQuery('직접 검색', statuteTopK + STATUTE_PAGE_SIZE)}
                >
                  {statuteLoading ? '불러오는 중…' : `조문 ${STATUTE_PAGE_SIZE}건 더 보기`}
                </button>
              ) : null}
            </div>
          </div>
          <div>
            <h3><ClipboardList size={16} strokeWidth={2.2} className="sectionIcon" aria-hidden="true" /> 검토에 반영할 자료</h3>
            {/* 담은 자료는 '읽는 것'이 아니라 '무엇을 담았는지 확인하는 것'이라,
                검색 결과 카드와 같은 크기로 그리면 한 건만 담아도 칸이 꽉 차
                몇 건을 담았는지 한눈에 안 들어옵니다. 한 줄짜리로 쌓습니다. */}
            <div className="referenceSelectedPanel compactList">
              {selected.length ? selected.map((item) => (
                <button type="button" key={item.id}
                  title={`${item.title} · 누르면 뺍니다`}
                  onClick={() => setSelected(selected.filter((value) => value.id !== item.id))}
                >
                  <span>{item.title}</span>
                  <strong aria-label="빼기">×</strong>
                </button>
              )) : <p>선택된 자료가 없습니다.</p>}
            </div>
          </div>
        </div>
      </section>
    </main>
  );
}
