package com.aivle.bigproject.document.dto;

import java.util.List;
import tools.jackson.databind.PropertyNamingStrategies;
import tools.jackson.databind.annotation.JsonNaming;

// note: 반려 사유 (필수). requestedMaterials: 상담원에게 추가로 요청하는 자료 목록
@JsonNaming(PropertyNamingStrategies.SnakeCaseStrategy.class)
public record RequestRevisionRequest(String note, List<String> requestedMaterials) {
}
