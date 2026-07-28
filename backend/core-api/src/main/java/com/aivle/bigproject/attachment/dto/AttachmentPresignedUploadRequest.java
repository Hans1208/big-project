package com.aivle.bigproject.attachment.dto;

// 프론트가 S3에 직접 업로드하기 전, "이 파일 올릴 presigned URL 주세요" 요청 body.
// frontend/src/services/s3UploadClient.js의 requestPresignedUpload가 보내는 형태와 일치.
public record AttachmentPresignedUploadRequest(
        String fileName,
        String contentType,
        String fileType
) {
}
