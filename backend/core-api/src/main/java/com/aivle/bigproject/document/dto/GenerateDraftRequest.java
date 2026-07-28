package com.aivle.bigproject.document.dto;

import tools.jackson.databind.PropertyNamingStrategies;
import tools.jackson.databind.annotation.JsonNaming;

// 상담원이 recommend-forms 응답 중 실제로 고른 서식명
@JsonNaming(PropertyNamingStrategies.SnakeCaseStrategy.class)
public record GenerateDraftRequest(String formName) {
}
