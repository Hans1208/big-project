package com.aivle.bigproject.analysis.dto;

import tools.jackson.databind.PropertyNamingStrategies;
import tools.jackson.databind.annotation.JsonNaming;

// 분석 결과 승인/반려 요청 공통 body. note: 승인 코멘트 또는 반려 사유(선택)
@JsonNaming(PropertyNamingStrategies.SnakeCaseStrategy.class)
public record AnalysisReviewRequest(String note) {
}
