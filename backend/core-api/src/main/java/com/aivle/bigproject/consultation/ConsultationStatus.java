package com.aivle.bigproject.consultation;

// 상담 진행 상태. 생성 시 항상 RECEIVED로 시작.
public enum ConsultationStatus {
    RECEIVED,   // 접수됨
    ANALYZING,  // AI 분석 중
    COMPLETED,  // 완료
    HOLD        // 보류 (내담자 연락두절, 추가자료 대기 등 상담 자체가 잠시 멈춘 상태 — 검토워크플로우의 반려와는 별개)
}
