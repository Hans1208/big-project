package com.aivle.bigproject.attachment.dto;

// 프론트가 presigned URL로 S3에 이미 올린 파일의 메타데이터를 기존 상담에 등록할 때 쓰는 요청 body.
// (상담 생성 시 함께 넘어오는 ConsultationRequest.AttachmentRegistration과 같은 모양 — 신규 상담 생성 때는
// ConsultationService.create()가 처리하고, 기존 상담에 자료를 "추가"할 때는 이 DTO로 별도 등록한다.)
public record AttachmentRegistrationRequest(
        String fileName,
        String fileType,
        String fileKey,
        String fileUrl,
        String contentType
) {
}
