package com.aivle.bigproject.attachment;

import org.springframework.data.jpa.repository.JpaRepository;

public interface AttachmentRepository extends JpaRepository<Attachment, Long> {

    // 아직 어떤 Attachment로도 등록되지 않은 S3 key인지 확인할 때 씀
    // (AttachmentService.deleteUnregistered 참고 — 이미 정식 등록된 파일을 실수로 지우지 않기 위한 안전장치)
    boolean existsByStorageKey(String storageKey);
}
