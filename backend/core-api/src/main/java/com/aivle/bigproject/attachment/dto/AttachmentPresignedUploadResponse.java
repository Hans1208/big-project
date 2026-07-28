package com.aivle.bigproject.attachment.dto;

// frontend/src/services/s3UploadClient.js가 그대로 기대하는 필드명(uploadUrl/fileKey/fileUrl).
// 이 시점엔 아직 DB에 아무것도 저장하지 않음 — 실제 등록은 상담 생성 시 attachments[].fileKey로 넘어옴.
public record AttachmentPresignedUploadResponse(
        String uploadUrl,
        String fileKey,
        String fileUrl
) {
}
