import React from 'react';
import { Radio, FileAudio2, ChevronRight, Check } from 'lucide-react';

// 오른쪽 2단계 카드는 예전엔 왼쪽 문단이 말로 설명하는 내용을 그림으로 다시 보여주기만 해서
// 있으나 마나 했습니다. 지금은 '지금 여기' 표시뿐 아니라, 지금 있지 않은 단계를 눌러 바로
// 넘어갈 수 있는 작은 스텝 네비게이션으로 씁니다(상단 메뉴까지 갈 필요 없이 화면 안에서 전환).
export function CounselorFlowStage({ current = 'realtime', onNavigate }) {
  // 통화를 받으면서 곧바로 진행하는 실시간 상담이 먼저이고, 문서 업로드는 통화가 끝난 뒤
  // 자료를 정리해 변호사 검토로 넘기는 후처리 단계입니다. (코치 피드백: 실시간 중심으로 순서 변경)
  const stages = [
    {
      key: 'realtime',
      icon: Radio,
      title: '실시간 상담',
      detail: '통화 시작 · 메모 · AI 분석',
    },
    {
      key: 'upload',
      icon: FileAudio2,
      title: '상담 자료 올리기',
      detail: '통화 후 자료 정리 · 변호사 검토 전달',
    },
  ];
  const activeIndex = Math.max(0, stages.findIndex((stage) => stage.key === current));

  return (
    <section className="flowStageBanner" aria-label="상담원 업무 단계">
      {/* 상담 자료 올리기 안내 카드 옆으로 옮기면서 자리가 좁아져, 왼쪽 안내 문구 박스는
          잠시 주석 처리합니다(단계 카드만으로도 지금 위치를 알 수 있어 없어도 됨). */}
      {/* <div className="flowStageCopy">
        <span className="flowStageEyebrow">상담원 업무 흐름</span>
        <strong>{current === 'upload' ? '통화 후 자료를 정리합니다.' : '통화 중 바로 기록합니다.'}</strong>
        <p>
          {current === 'upload'
            ? '녹취·이미지·문서를 추가하고 저장하면, 오른쪽 2단계에서 바로 변호사 검토로 전달할 수 있어요.'
            : '통화를 시작하고 메모를 남기면, 상담이 끝난 뒤 다음 단계(자료 올리기)로 이어집니다.'}
        </p>
      </div> */}
      <div className="flowStageSteps">
        {stages.map((stage, index) => {
          const Icon = stage.icon;
          const active = current === stage.key;
          const complete = index < activeIndex;
          const canNavigate = !active && Boolean(onNavigate);
          return (
            <article
              className={`flowStageStep${active ? ' active' : ''}${complete ? ' complete' : ''}${canNavigate ? ' linkable' : ''}`}
              key={stage.key}
              {...(canNavigate ? {
                role: 'button',
                tabIndex: 0,
                onClick: onNavigate,
                onKeyDown: (event) => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); onNavigate(); } },
              } : {})}
            >
              <span className="flowStageIndex" aria-label={complete ? `${index + 1}단계 완료` : `${index + 1}단계`}>
                {complete ? <Check size={15} strokeWidth={3} aria-hidden="true" /> : index + 1}
              </span>
              <div className="flowStageText">
                <strong><Icon size={15} strokeWidth={2.2} /> {stage.title}</strong>
                <small>{stage.detail}</small>
              </div>
              {active ? <em className="flowStageHereBadge">현재 화면</em> : null}
              {canNavigate ? <ChevronRight className="flowStageGo" size={16} strokeWidth={2.4} aria-hidden="true" /> : null}
            </article>
          );
        })}
      </div>
    </section>
  );
}
