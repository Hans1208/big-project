package com.aivle.bigproject.storage;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import software.amazon.awssdk.auth.credentials.AwsBasicCredentials;
import software.amazon.awssdk.auth.credentials.AwsCredentialsProvider;
import software.amazon.awssdk.auth.credentials.DefaultCredentialsProvider;
import software.amazon.awssdk.auth.credentials.StaticCredentialsProvider;
import software.amazon.awssdk.regions.Region;
import software.amazon.awssdk.services.s3.S3Client;

// S3Client 빈을 만드는 설정 클래스.
// FileStorageService(로컬)와는 완전히 독립적 — 이 설정이 없어도 로컬 저장은 그대로 동작함.
@Configuration
public class S3Config {

    @Value("${app.s3.region}")
    private String region;

    @Value("${app.s3.access-key:}")
    private String accessKey;

    @Value("${app.s3.secret-key:}")
    private String secretKey;

    // S3Client뿐 아니라 S3FileStorageService의 S3Presigner(presigned URL 발급)도 이 빈을 그대로 써야 함.
    // 따로 만들면 presigner가 app.s3.access-key 대신 AWS 기본 자격증명 체인(env var 등)만 보게 되어
    // "yaml엔 access-key를 채웠는데 presign만 인증 실패"하는 상황이 생김.
    @Bean
    public AwsCredentialsProvider awsCredentialsProvider() {
        return (accessKey != null && !accessKey.isBlank())
                ? StaticCredentialsProvider.create(AwsBasicCredentials.create(accessKey, secretKey))
                : DefaultCredentialsProvider.create(); // access-key 없으면 IAM role 등 기본 체인 사용
    }

    @Bean
    public S3Client s3Client(AwsCredentialsProvider awsCredentialsProvider) {
        return S3Client.builder()
                .region(Region.of(region))
                .credentialsProvider(awsCredentialsProvider)
                .build();
    }
}