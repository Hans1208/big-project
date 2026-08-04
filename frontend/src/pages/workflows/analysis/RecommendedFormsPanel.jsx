import React, { useState, useEffect } from 'react';
import { Sparkles, FileText, Star } from 'lucide-react';
import { cacheFormRecommendations, readCachedFormRecommendations } from '../../../services/draftDocumentStore.js';
import { recommendCoreForms } from '../../../services/coreApiClientV2.js';
import { recommendTemplates } from '../../../services/legalAidApi.js';
import { resolveConfirmedCaseType } from '../shared/caseHelpers.js';

// 코치 피드백: "실시간 상담 때 서식을 추천 및 초안 작성을 해주고". 분석이 끝나면 곧바로
// 이 화면 안에서 추천 서식을 보여주고, 한 번의 클릭으로 사건이 선택된 채 서식 생성 화면으로
// 넘어가게 합니다(예전엔 메뉴를 옮겨 사건을 다시 골라야 했습니다).
// coreId·분석id가 있으면 실제 ai-api 추천(recommendCoreForms)을, 없으면 로컬 휴리스틱
// (recommendTemplates, DraftWorkbench와 같은 함수)을 그대로 재사용합니다.
// 서식 추천을 가져옵니다. 실시간 상담 분석 화면과 서식 생성 화면이 같이 씁니다.
//
// 예전엔 두 화면이 각자 recommendCoreForms를 불러서, 분석 화면에서 추천을 본 뒤
// 초안 만들기로 넘어가면 같은 상담·같은 분석인데도 처음부터 다시 돌렸습니다
// (ai-api 임베딩 검색 + GPT 재랭킹이라 몇 초 걸립니다).
//
// 순서대로 찾습니다.
//   1) 저장된 분석의 recommendation_json — 새로고침해도 남아 있는 유일한 자리
//   2) 이번 세션 메모리 캐시 — 아직 저장 전이라도 화면 사이를 오갈 때 재사용
//   3) 없으면 API 호출 후 두 곳에 모두 남김
export function useFormRecommendations(selectedCase) {
  const coreId = selectedCase?.coreId;
  const analysisId = selectedCase?.coreAnalysisId;
  const canUseCoreApi = Boolean(coreId && analysisId);
  // 저장된 분석에 이미 추천이 들어 있으면 그걸 그대로 씁니다.
  const savedRecommendations = selectedCase?.analysis?.recommendation?.recommendations;

  const initial = (Array.isArray(savedRecommendations) && savedRecommendations.length)
    ? savedRecommendations
    : (readCachedFormRecommendations(coreId, analysisId) || []);

  const [aiRecommendations, setAiRecommendations] = useState(initial);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!canUseCoreApi) { setAiRecommendations([]); return undefined; }

    if (Array.isArray(savedRecommendations) && savedRecommendations.length) {
      cacheFormRecommendations(coreId, analysisId, savedRecommendations);
      setAiRecommendations(savedRecommendations);
      return undefined;
    }
    const cached = readCachedFormRecommendations(coreId, analysisId);
    if (cached) { setAiRecommendations(cached); return undefined; }

    let cancelled = false;
    setAiRecommendations([]);
    setLoading(true);
    recommendCoreForms(coreId, analysisId)
      .then((response) => {
        const list = response?.recommendations || [];
        cacheFormRecommendations(coreId, analysisId, list);
        if (!cancelled) setAiRecommendations(list);
      })
      .catch(() => { if (!cancelled) setAiRecommendations([]); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [canUseCoreApi, coreId, analysisId, savedRecommendations]);

  return { aiRecommendations, loading };
}

export function RecommendedFormsPanel({ selectedCase, onSaveBeforeOpen, saving }) {
  const draftCaseType = resolveConfirmedCaseType(selectedCase);
  const { aiRecommendations, loading } = useFormRecommendations(selectedCase);

  // 실제 ai-api 추천이 있으면 'AI 추천' 배지를, 없어 로컬 휴리스틱으로 대체한 경우는
  // '추천' 배지로 구분해 어떤 근거로 골랐는지 헷갈리지 않게 합니다.
  const usingAiRecommendations = Boolean(aiRecommendations.length);
  const localTemplateNames = draftCaseType ? recommendTemplates(draftCaseType).map((item) => item.templateName) : [];
  const templateNames = (usingAiRecommendations
    ? aiRecommendations.map((item) => item.form_name).filter(Boolean)
    : localTemplateNames
  ).slice(0, 3);

  return (
    <section className="recommendedFormsPanel">
      <div className="recommendedFormsHeader">
        <div>
          <h3><Sparkles size={16} strokeWidth={2.2} className="sectionIcon" aria-hidden="true" /> 추천 서식</h3>
          <p>{draftCaseType ? `${draftCaseType} 기준 추천` : '사건 유형 확정 후 추천'}</p>
        </div>
      </div>
      {loading ? <p className="helperText">추천 서식을 불러오는 중…</p> : null}
      {templateNames.length ? (
        <div className="recommendedFormsList">
          {templateNames.map((name) => (
            <div className="tmplRow" key={name}>
              <span className="tmplRowName">
                <FileText size={14} strokeWidth={2.2} aria-hidden="true" /> {name}
                <em className={`tmplRowBadge statusChip ${usingAiRecommendations ? 'tone-info' : 'tone-muted'}`}>
                  {usingAiRecommendations ? <Star size={11} strokeWidth={2.4} aria-hidden="true" /> : null} {usingAiRecommendations ? 'AI 추천' : '추천'}
                </em>
              </span>
              {/* 넘어가기 전에 저장까지 합니다. 예전엔 저장을 따로 눌러야 했고, 안 누르고
                  넘어가면 서식 화면에서 분석 결과 없이 시작해 추천이 로컬 휴리스틱으로
                  떨어졌습니다. 저장 버튼과 같은 함수(performSaveAnalysis)를 부르므로
                  저장 경로가 둘로 갈리지 않습니다. */}
              {/* 예전엔 추천 서식 3개 중 무엇을 눌러도 항상 caseId만 넘겨서, 서식 생성
                  화면은 어느 걸 눌렀는지 모르고 매번 같은(초기) 서식으로 열렸습니다
                  (코치 피드백). 어떤 서식을 눌렀는지도 함께 넘깁니다. */}
              <button
                type="button"
                className="secondaryActionButton compactAction"
                onClick={() => onSaveBeforeOpen?.(selectedCase.id, name)}
                disabled={!onSaveBeforeOpen || saving}
              >
                {saving ? '저장하는 중...' : '저장하고 초안 만들기'}
              </button>
            </div>
          ))}
        </div>
      ) : <p className="helperText">분석 저장 후 추천 가능</p>}
    </section>
  );
}
