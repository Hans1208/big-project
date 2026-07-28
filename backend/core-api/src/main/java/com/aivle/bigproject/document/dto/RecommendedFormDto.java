package com.aivle.bigproject.document.dto;

import tools.jackson.databind.PropertyNamingStrategies;
import tools.jackson.databind.annotation.JsonNaming;

// ai-api /forms/recommend 응답의 recommendations 배열 원소 하나
@JsonNaming(PropertyNamingStrategies.SnakeCaseStrategy.class)
public record RecommendedFormDto(
        Integer rank,
        String formName,
        String reason
) {
}
