package com.aivle.bigproject.analysis;

// AI 분석 결과 검토 상태.
// DRAFTED: 상담원이 확인/수정 중 (아직 검토 요청 전)
// SUBMITTED_FOR_REVIEW: 검토 요청함
// APPROVED: 승인 완료 — 이후 서식 추천/초안 생성에 쓰이는 확정 버전
// REVISION_REQUESTED: 반려 -> 상담원이 다시 수정 후 재제출해야 함
// GeneratedDocument.DocumentReviewStatus와 상태 이름은 같지만, 여기는 재제출 시 AI 재생성이
// 없고(상담원이 직접 고친 값을 그대로 씀) 개념적으로 별개 도메인이라 enum도 따로 둔다.
public enum AnalysisReviewStatus {
    DRAFTED,
    SUBMITTED_FOR_REVIEW,
    APPROVED,
    REVISION_REQUESTED
}
