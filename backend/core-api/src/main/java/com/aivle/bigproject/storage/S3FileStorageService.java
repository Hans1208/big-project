package com.aivle.bigproject.storage;

import java.io.IOException;
import java.io.UncheckedIOException;
import java.time.Duration;
import java.util.UUID;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.core.io.InputStreamResource;
import org.springframework.core.io.Resource;
import org.springframework.stereotype.Service;
import org.springframework.web.multipart.MultipartFile;
import software.amazon.awssdk.auth.credentials.AwsCredentialsProvider;
import software.amazon.awssdk.core.sync.RequestBody;
import software.amazon.awssdk.regions.Region;
import software.amazon.awssdk.services.s3.S3Client;
import software.amazon.awssdk.services.s3.model.DeleteObjectRequest;
import software.amazon.awssdk.services.s3.model.GetObjectRequest;
import software.amazon.awssdk.services.s3.model.PutObjectRequest;
import software.amazon.awssdk.services.s3.presigner.S3Presigner;
import software.amazon.awssdk.services.s3.presigner.model.GetObjectPresignRequest;
import software.amazon.awssdk.services.s3.presigner.model.PutObjectPresignRequest;

// 파일을 S3 버킷에 저장/조회/삭제하는 역할만 담당하는 클래스.
// FileStorageService(로컬)와 마찬가지로 Attachment 엔티티나 DB를 전혀 모름.
// 두 클래스는 서로 독립적 — 어느 한쪽을 지워도 다른 쪽은 그대로 동작함.
@Service
public class S3FileStorageService {

    private final S3Client s3Client;
    private final AwsCredentialsProvider credentialsProvider; // S3Client와 같은 자격증명을 presigner에도 그대로 씀
    private final String bucket;
    private final String region;

    public S3FileStorageService(S3Client s3Client,
                                AwsCredentialsProvider credentialsProvider,
                                @Value("${app.s3.bucket}") String bucket,
                                @Value("${app.s3.region}") String region) {
        this.s3Client = s3Client;
        this.credentialsProvider = credentialsProvider;
        this.bucket = bucket;
        this.region = region;
    }

    public String getBucket() {
        return bucket;
    }

    // 브라우저가 백엔드를 거치지 않고 S3에 직접 파일을 PUT할 수 있는 presigned URL을 발급.
    // 실제 오브젝트는 아직 존재하지 않음 — key는 여기서 미리 채번만 함.
    public record PresignedUpload(String key, String uploadUrl, String publicUrl) {}

    // TODO(규제): 파일명·contentType을 클라이언트가 준 그대로 서명하고 있음 — 검증 필요.
    //   시큐어코딩 가이드 "위험한 형식 파일 업로드" 항목. 확장자 화이트리스트, 확장자와
    //   contentType 일치 확인, 파일명의 경로문자(/ \)·개행 제거가 필요하다.
    //   실제 바이트는 S3로 직행해 서버를 거치지 않으므로 Spring의 multipart 제한이 걸리지 않는다.
    //   크기는 프론트 file.size 검사와 application.yaml 양쪽으로 막아야 한다.
    public PresignedUpload presignUpload(String originalFileName, String contentType, Duration expiration) {
        String key = "consult-attachments/" + UUID.randomUUID() + "__" + originalFileName;
        try (S3Presigner presigner = S3Presigner.builder().region(Region.of(region)).credentialsProvider(credentialsProvider).build()) {
            PutObjectRequest putObjectRequest = PutObjectRequest.builder()
                    .bucket(bucket)
                    .key(key)
                    .contentType(contentType)
                    .build();

            PutObjectPresignRequest presignRequest = PutObjectPresignRequest.builder()
                    .signatureDuration(expiration)
                    .putObjectRequest(putObjectRequest)
                    .build();

            String uploadUrl = presigner.presignPutObject(presignRequest).url().toString();
            String publicUrl = "https://%s.s3.%s.amazonaws.com/%s".formatted(bucket, region, key);
            return new PresignedUpload(key, uploadUrl, publicUrl);
        }
    }

    // 파일을 {상담ID}/{uuid}_{원본파일명} 형태의 key로 S3에 업로드하고, 그 key를 돌려줌
    // (로컬 버전의 "rootDir 기준 상대경로"에 대응하는 개념 — 이 key를 DB(Attachment.fileUrl)에 저장)
    public String store(Long consultationId, MultipartFile file) {
        String originalName = file.getOriginalFilename() != null ? file.getOriginalFilename() : "file";
        String key = consultationId + "/" + UUID.randomUUID() + "__" + originalName;

        try {
            s3Client.putObject(
                    PutObjectRequest.builder()
                            .bucket(bucket)
                            .key(key)
                            .contentType(file.getContentType())
                            .build(),
                    RequestBody.fromInputStream(file.getInputStream(), file.getSize())
            );
        } catch (IOException e) {
            throw new UncheckedIOException("S3 업로드에 실패했습니다: " + originalName, e);
        }

        return key;
    }

    // 저장된 파일을 다운로드용 Resource로 읽어옴 (스트리밍 방식으로 S3에서 직접 받아옴)
    public Resource loadAsResource(String key) {
        try {
            var s3Object = s3Client.getObject(
                    GetObjectRequest.builder()
                            .bucket(bucket)
                            .key(key)
                            .build()
            );
            return new InputStreamResource(s3Object);
        } catch (Exception e) {
            throw new UncheckedIOException("S3에서 파일을 읽을 수 없습니다: " + key,
                    new IOException(e));
        }
    }

    // 클라이언트가 서버를 거치지 않고 S3에서 바로 다운로드할 수 있는 임시 URL 발급
    // (대용량 파일 다운로드 시 서버 부하를 줄이고 싶을 때 사용 — 필요 없으면 이 메서드만 안 쓰면 됨)
    public String getPresignedDownloadUrl(String key, Duration expiration) {
        try (S3Presigner presigner = S3Presigner.builder().region(Region.of(region)).credentialsProvider(credentialsProvider).build()) {
            GetObjectRequest getObjectRequest = GetObjectRequest.builder()
                    .bucket(bucket)
                    .key(key)
                    .build();

            GetObjectPresignRequest presignRequest = GetObjectPresignRequest.builder()
                    .signatureDuration(expiration)
                    .getObjectRequest(getObjectRequest)
                    .build();

            return presigner.presignGetObject(presignRequest).url().toString();
        }
    }

    // 파일 삭제. Consultation/Attachment 삭제 시 같이 호출됨.
    public void delete(String key) {
        s3Client.deleteObject(
                DeleteObjectRequest.builder()
                        .bucket(bucket)
                        .key(key)
                        .build()
        );
    }
}