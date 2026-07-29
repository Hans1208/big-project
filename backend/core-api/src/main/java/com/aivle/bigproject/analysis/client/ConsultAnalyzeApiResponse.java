package com.aivle.bigproject.analysis.client;

import tools.jackson.databind.JsonNode;
import tools.jackson.databind.PropertyNamingStrategies;
import tools.jackson.databind.annotation.JsonNaming;

// ai-api의 POST /consult/analyze 응답 (ConsultAnalyzeResponse 스키마).
// 중첩 블록은 Java 레코드로 전부 다시 타이핑하지 않고 JsonNode로 얕게 받아서,
// AiAnalysisService가 필요한 값만 .path()로 꺼내 쓰고 나머지는 통째로 jsonb 컬럼에 저장한다
// (AiAnalysisRequest/Response가 jsonb 컬럼을 JsonNode로 주고받는 것과 같은 패턴).
@JsonNaming(PropertyNamingStrategies.SnakeCaseStrategy.class)
public record ConsultAnalyzeApiResponse(
        JsonNode rawInput,
        // ai-api의 analysis 층(app/ai/analysis) 구조화 결과 — AI_ANALYSIS 계약 필드에 1:1 대응.
        // 구조화가 실패했거나 아직 이 필드를 안 주는 버전의 ai-api면 null이 온다.
        // case_type은 오지 않는다: analysis 층은 가사사건 4대분류, consult 층은 8개 유형이라
        // 체계가 달라서 시스템 범위가 확정될 때까지 섞지 않기로 함.
        String consultSummary,
        String consultCaseType,
        String consultCaseSubtype,
        JsonNode consultExtracted,
        JsonNode consultTimeline,
        JsonNode caseAnalysis,
        JsonNode reliefReviewChecklist,
        JsonNode missingItems
) {
}
