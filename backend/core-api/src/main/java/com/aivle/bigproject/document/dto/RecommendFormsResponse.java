package com.aivle.bigproject.document.dto;

import java.util.List;
import tools.jackson.databind.PropertyNamingStrategies;
import tools.jackson.databind.annotation.JsonNaming;

// ai-api POST /forms/recommend 응답을 그대로 프론트로 전달하는 형태.
// DB엔 저장하지 않는다 — 상담원이 실제로 서식을 고르기 전까지는 확정된 게 아니라서(HITL).
@JsonNaming(PropertyNamingStrategies.SnakeCaseStrategy.class)
public record RecommendFormsResponse(
        List<RecommendedFormDto> recommendations,
        Integer candidatesCount,
        String reasonIfEmpty
) {
}
