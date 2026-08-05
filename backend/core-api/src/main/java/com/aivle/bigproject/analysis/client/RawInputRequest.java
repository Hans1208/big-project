package com.aivle.bigproject.analysis.client;

import java.util.List;
import tools.jackson.databind.PropertyNamingStrategies;
import tools.jackson.databind.annotation.JsonNaming;

// ai-api app/agents/consult/schemas.py의 RawInput/RawInputContent를 그대로 미러링한 요청 body.
// summitedFileLink는 ai-api 쪽 필드명(summited_file_link)의 오타를 그대로 유지한 것 — 여기서
// "고치면" snake_case 변환 결과가 달라져서 ai-api가 그 필드를 못 알아봄.
@JsonNaming(PropertyNamingStrategies.SnakeCaseStrategy.class)
public record RawInputRequest(RawInputContent content) {

    @JsonNaming(PropertyNamingStrategies.SnakeCaseStrategy.class)
    public record RawInputContent(
            String summary,
            String details,
            List<String> summitedFileLink,
            String consultDay,
            String anonymizedText
    ) {
    }
}
