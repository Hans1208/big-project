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
        JsonNode caseAnalysis,
        JsonNode reliefReviewChecklist,
        JsonNode missingItems
) {
}
