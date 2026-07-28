package com.aivle.bigproject.document.dto;

import tools.jackson.databind.PropertyNamingStrategies;
import tools.jackson.databind.annotation.JsonNaming;

// 승인 코멘트는 선택 사항
@JsonNaming(PropertyNamingStrategies.SnakeCaseStrategy.class)
public record ApproveRequest(String note) {
}
