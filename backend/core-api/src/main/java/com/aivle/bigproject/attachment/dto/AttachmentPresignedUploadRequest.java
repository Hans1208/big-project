package com.aivle.bigproject.attachment.dto;

// 프론트가 S3에 직접 업로드하기 전, "이 파일 올릴 presigned URL 주세요" 요청 body.
// frontend/src/services/s3UploadClient.js의 requestPresignedUpload가 보내는 형태와 일치.
//
// sizeBytes는 브라우저가 알려주는 file.size다. 파일 바이트가 서버를 지나지 않아 실제 크기를
// 확인할 방법이 없으므로 이 값으로 1차만 거른다 — 클라이언트가 준 값이라 신뢰할 수는 없고,
// 확실한 상한은 S3 버킷 정책이나 업로드 후 검사로 걸어야 한다.
// 값을 보내지 않는 호출부도 있어 null을 허용한다(그 경우 크기 검사는 건너뛴다).
public record AttachmentPresignedUploadRequest(
        String fileName,
        String contentType,
        String fileType,
        Long sizeBytes
) {
}
