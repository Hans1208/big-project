package com.aivle.bigproject.document;

// 서식 초안 검토 상태.
// DRAFTED: 상담원이 초안만 생성한 직후 (아직 변호사에게 안 보냄)
// SUBMITTED_FOR_REVIEW: 변호사에게 검토 요청함
// APPROVED: 변호사 승인 완료
// REVISION_REQUESTED: 변호사가 추가자료/수정 요청 -> 상담원이 보완 후 재제출해야 함
public enum DocumentReviewStatus {
    DRAFTED,
    SUBMITTED_FOR_REVIEW,
    APPROVED,
    REVISION_REQUESTED
}
