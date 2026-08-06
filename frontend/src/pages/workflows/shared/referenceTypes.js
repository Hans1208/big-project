// 검토 자료의 종류별 표기를 한 곳에 모읍니다.
//
// 원래는 화면마다 `type === 'precedent' ? '판례' : '법령'` 삼항식이 흩어져 있었습니다.
// 자료가 둘일 때는 그래도 됐지만 상담사례가 붙어 셋이 되면서, 그 삼항식들이 전부
// 상담사례를 '법령'으로 표시하게 됐습니다 — 담은 자료 화면, 변호사 검토 근거,
// 저장본 복원 세 군데가 동시에 틀렸습니다.
//
// 네 번째 자료가 붙을 때 또 같은 일이 나지 않도록 여기만 고치면 되게 둡니다.
export const REFERENCE_TYPES = {
  statute: {
    label: '법령',
    // 법령은 시행일, 판례는 선고일, 상담사례는 자료 기준일이 같은 자리에 옵니다.
    dateLabel: '시행',
    // 담은 자료 화면에서 원문을 펼치는 버튼 문구.
    bodyToggleLabel: '조문 전문 보기',
  },
  precedent: {
    label: '판례',
    dateLabel: '선고',
    // 판례 카드에 실리는 것은 판결문이 아니라 판시사항입니다.
    bodyToggleLabel: '판시사항 보기',
  },
  similar: {
    label: '상담사례',
    dateLabel: '기준',
    bodyToggleLabel: '답변 보기',
  },
};

// 모르는 종류가 와도 화면이 죽지 않게 법령으로 떨어뜨립니다. 예전에 저장된
// 자료에는 type이 아예 없을 수 있습니다(자료가 법령뿐이던 시절에 담은 것).
export function referenceTypeMeta(type) {
  return REFERENCE_TYPES[type] || REFERENCE_TYPES.statute;
}

export function referenceTypeLabel(type) {
  return referenceTypeMeta(type).label;
}
