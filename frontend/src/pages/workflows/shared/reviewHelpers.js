// 변호사 검토 결과 배너의 좌측 색 바를 결정 종류에 맞게 고릅니다(승인=그린/반려=레드/그 외=옐로).
export function reviewActionTone(status) {
  if (status === '승인') return 'success';
  if (status === '반려') return 'danger';
  return 'warn';
}
// checklist_summary_for_lawyer는 "[구조대상자 여부] 대상 (...)\n[승소가능성] ...\n※ 위 내용은..."
// 형태의 한 덩어리 문자열입니다. 항목별 대괄호 태그가 그대로 화면에 보이면 읽기 어려우므로,
// 줄 단위로 "[라벨] 내용" 패턴을 잘라 label/value 목록으로 만들고, 맨 끝 "※..." 안내문은 따로
// 분리해 각주로 둡니다. 값이 빈 항목(해당 신호에 review_note가 없던 경우)은 목록에서 뺍니다.
export function parseLawyerSummary(rawText = '') {
  const footnoteIndex = rawText.indexOf('※');
  const bodyText = footnoteIndex >= 0 ? rawText.slice(0, footnoteIndex) : rawText;
  const footnote = footnoteIndex >= 0 ? rawText.slice(footnoteIndex).trim() : '';
  const items = bodyText
    .split('\n')
    .map((line) => {
      const match = line.match(/^\[([^\]]+)\]\s*(.*)$/);
      if (!match) return null;
      const value = match[2].trim();
      return value ? { label: match[1].trim(), value } : null;
    })
    .filter(Boolean);
  return { items, footnote };
}
// 체크박스 5항목(법률구조 대상 여부/증빙/승소가능성/집행가능성/구조타당성) 옆에 AI 근거를 한 줄
// 덧붙입니다. 체크 여부(checked)는 절대 건드리지 않습니다 — 상담원이 직접 확인하고 체크하는
// 항목이라는 HITL 원칙은 그대로이고, 이건 표시 전용 참고 문구입니다. requestEligibilityCandidate
// 등 기존 코드가 이미 쓰는 item.label.includes(...) 매칭 방식을 그대로 따릅니다.
export function checklistItemNote(item, detail) {
  if (!detail) return null;
  if (item.label.includes('대상자 증빙서류')) {
    const evidence = detail.eligibility;
    if (!evidence) return null;
    const requiredEvidence = evidence.requiredEvidence.join(', ');
    const statusText = evidence.evidenceStatus === '충족' ? '제출 확인됨'
      : evidence.evidenceStatus === '미비' ? '미제출' : '확인불가';
    return requiredEvidence ? `${requiredEvidence} ${statusText}` : null;
  }
  if (item.label.includes('대상 여부')) return detail.eligibility?.judgmentNote || null;
  if (item.label.includes('승소 가능성')) return detail.winnability?.reviewNote || null;
  if (item.label.includes('집행 가능성')) return detail.executability?.reviewNote || null;
  if (item.label.includes('구조 타당성')) return detail.appropriateness?.reviewNote || null;
  return null;
}

// 위험 신호는 노트 문장에 묻히면 놓치기 쉬워 별도 칩으로 뺍니다 — ReliefReviewDetailTabs의 탭 점
// (categoryTabDot)과 같은 두 조건을 그대로 씁니다.
export function checklistItemFlag(item, detail) {
  if (!detail) return null;
  if (item.label.includes('승소 가능성') && detail.winnability?.statuteOfLimitationsFlag === '계산 불가') {
    return { text: '소멸시효 계산 불가', tone: 'tone-warn' };
  }
  if (item.label.includes('구조 타당성') && (detail.appropriateness?.personalMotiveFlags || []).length) {
    return { text: detail.appropriateness.personalMotiveFlags.join(', '), tone: 'tone-danger' };
  }
  return null;
}

// null을 함부로 '미충족'/'언급 없음'으로 해석하지 않기 위한 3단계 라벨. income_criterion_met 같은
// 필드는 true/false/null(=아직 판단 불가) 셋을 구분해서 받는데, null을 false 취급하면 실제로는
// 판단이 안 된 사건을 '탈락'으로 잘못 보여주게 됩니다.
export function criterionLabel(value) {
  if (value === true) return '충족';
  if (value === false) return '미충족';
  return '판단 보류';
}

export function mentionLabel(value) {
  if (value === true) return '언급됨';
  if (value === false) return '언급 없음';
  return '미확인';
}

export function evidenceStatusTone(status) {
  if (status === '충족') return 'tone-success';
  if (status === '미비') return 'tone-warn';
  return 'tone-muted';
}
