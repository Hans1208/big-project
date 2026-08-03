package com.aivle.bigproject.analysis.job.dto;

import com.aivle.bigproject.analysis.job.AnalysisJobStatus;
import java.time.LocalDateTime;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.PropertyNamingStrategies;
import tools.jackson.databind.annotation.JsonNaming;

// 분석 작업의 현재 상태. 화면은 이걸 주기적으로 받아보며 기다린다.
//
// result는 SUCCEEDED일 때만 채워지고, 그 안의 모양은 기존 POST .../analyze 응답
// (AiAnalysisResponse)과 완전히 같다. 그래야 프론트에서 결과를 다루는 코드를 안 고쳐도 된다.
@JsonNaming(PropertyNamingStrategies.SnakeCaseStrategy.class)
public record AnalysisJobResponse(
        Long jobId,
        Long consultationId,
        AnalysisJobStatus status,
        JsonNode result,
        String errorMessage,
        LocalDateTime createdAt,
        LocalDateTime startedAt,
        LocalDateTime finishedAt
) {
}
