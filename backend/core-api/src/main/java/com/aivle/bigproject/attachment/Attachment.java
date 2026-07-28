package com.aivle.bigproject.attachment;

import com.aivle.bigproject.consultation.Consultation;
import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.EntityListeners;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.JoinColumn;
import jakarta.persistence.ManyToOne;
import java.time.LocalDateTime;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;
import org.springframework.data.annotation.CreatedDate;
import org.springframework.data.jpa.domain.support.AuditingEntityListener;

// 상담에 딸린 첨부파일 (녹음파일, 증빙서류 등). 상담 1건에 여러 개 가능 (N:1의 N쪽).
@Entity
@Getter
@Setter
@NoArgsConstructor
@EntityListeners(AuditingEntityListener.class)
public class Attachment {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    // 이 파일이 속한 상담. FK 컬럼명은 consultation_id.
    // 기본적으로 @ManyToOne은 EAGER 로딩이라 항상 같이 조회됨 (LAZY인 attachments 리스트와는 다름).
    @ManyToOne
    @JoinColumn(name = "consultation_id", nullable = false)
    private Consultation consultation;

    @Column(name = "file_name", nullable = false)
    private String fileName; // 업로드 당시의 원본 파일명

    // 파일 종류. ERD에 "음성/계약서/이미지/PDF 등"으로 열려있게 나와 있어서
    // 고정된 enum이 아니라 자유 문자열로 둠 (나중에 종류가 늘어나도 코드 수정 불필요)
    @Column(name = "file_type", nullable = false)
    private String fileType;

    // 사람이 읽는 참고용 URL. 실제 다운로드/삭제/ai-api 전달은 storageKey 기준으로 함.
    @Column(name = "file_url", nullable = false)
    private String fileUrl;

    // 실제 저장된 S3 버킷/키. ai-api의 /consult/analyze 호출 시 summited_file_link로
    // 이 storageKey가 그대로 전달됨 (S3FileStorageService 참고).
    @Column(name = "storage_bucket")
    private String storageBucket;

    @Column(name = "storage_key")
    private String storageKey;

    @Column(name = "content_type")
    private String contentType;

    // STT(음성→텍스트)나 OCR(이미지→텍스트) 결과가 들어갈 자리.
    // 지금은 업로드 시점에 채우는 로직이 없어서 항상 null. 나중에 ai-api 연동 시 채워질 예정.
    // @Lob을 안 붙이는 이유는 Consultation.inputText 주석 참고 (Postgres text + @Lob(String) 조합의
    // OID 저장 버그 회피).
    // @Lob은 쓰지 않는다 — AiAnalysis.summary 주석 참고.
    @Column(name = "extracted_text", columnDefinition = "TEXT")
    private String extractedText;

    @CreatedDate
    @Column(nullable = false, updatable = false)
    private LocalDateTime uploadedAt;

    public Attachment(Consultation consultation, String fileName, String fileType, String fileUrl,
                       String storageBucket, String storageKey, String contentType) {
        this.consultation = consultation;
        this.fileName = fileName;
        this.fileType = fileType;
        this.fileUrl = fileUrl;
        this.storageBucket = storageBucket;
        this.storageKey = storageKey;
        this.contentType = contentType;
    }
}
