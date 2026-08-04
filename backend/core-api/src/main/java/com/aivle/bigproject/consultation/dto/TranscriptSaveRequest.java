package com.aivle.bigproject.consultation.dto;

// "상담 저장" 버튼 전용 요청 body. 실시간 상담(전화/대면) 채널별 현재 메모를 그대로 받아
// Consultation.input_text를 갱신하고 call_input_texts/inperson_input_texts(_masked)에
// 스냅샷을 append한다(ConsultationService.saveTranscript 참고).
//
// AiAnalysisRequest(분석 결과 저장)와는 완전히 분리된 경로다 — "분석 내용 저장"은 ai_analysis
// 테이블만 건드리고 Consultation은 건드리지 않는다는 요구에 따라, 상담 원문 저장은 이 엔드포인트가
// 전담한다.
//
// 같은 컨트롤러의 ConsultationRequest와 마찬가지로 @JsonNaming(SnakeCase)을 쓰지 않는다 —
// AiAnalysisRequest(analyses 하위 리소스, ai_analysis 계약과 맞춤)와 달리 이 컨트롤러의 기존
// 요청 바디는 전부 camelCase 그대로다.
public record TranscriptSaveRequest(
        String callInputText,
        String callInputTextMasked,
        String inpersonInputText,
        String inpersonInputTextMasked
) {
}
