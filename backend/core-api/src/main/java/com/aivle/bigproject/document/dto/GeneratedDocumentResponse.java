package com.aivle.bigproject.document.dto;

import com.aivle.bigproject.document.DocumentReviewStatus;
import java.time.LocalDateTime;
import java.util.List;
import tools.jackson.databind.PropertyNamingStrategies;
import tools.jackson.databind.annotation.JsonNaming;

@JsonNaming(PropertyNamingStrategies.SnakeCaseStrategy.class)
public record GeneratedDocumentResponse(
        Long documentId,
        Long consultationId,
        String formName,
        String recommendationReason,
        String draftFilePath,
        DocumentReviewStatus status,
        Long reviewerId,
        String reviewerName,
        String reviewNote,
        List<String> requestedMaterials,
        LocalDateTime reviewedAt,
        int revisionCount,
        LocalDateTime createdAt
) {
}
