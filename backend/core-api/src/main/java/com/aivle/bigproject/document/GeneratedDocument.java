package com.aivle.bigproject.document;

import com.aivle.bigproject.consultation.Consultation;
import com.aivle.bigproject.user.User;
import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.EntityListeners;
import jakarta.persistence.EnumType;
import jakarta.persistence.Enumerated;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.JoinColumn;
import jakarta.persistence.ManyToOne;
import jakarta.persistence.Table;
import java.time.LocalDateTime;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;
import org.hibernate.annotations.JdbcTypeCode;
import org.hibernate.type.SqlTypes;
import org.springframework.data.annotation.CreatedDate;
import org.springframework.data.jpa.domain.support.AuditingEntityListener;

// ai-api(/forms/draft)가 생성한 서식 초안 결과 저장. AiAnalysis와 같은 패턴(단방향 N:1 FK) —
// 한 상담에 여러 초안이 생길 수 있다고 보고 N:1로 설계함.
// 추천 목록(/forms/recommend 결과)은 여기 저장하지 않는다 — 상담원이 실제로 서식을 골라
// 초안까지 만들기 전까지는 확정된 게 아니므로(HITL), DocumentController가 그때그때
// ai-api를 호출해 응답만 돌려주고 DB에는 안 남긴다.
@Entity
@Table(name = "generated_document")
@Getter
@Setter
@NoArgsConstructor
@EntityListeners(AuditingEntityListener.class)
public class GeneratedDocument {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @ManyToOne
    @JoinColumn(name = "consultation_id", nullable = false)
    private Consultation consultation;

    @Column(name = "form_name", nullable = false)
    private String formName;

    // 상담원이 이 서식을 고를 때 ai-api가 제시했던 추천 근거(있으면)
    // @Lob은 쓰지 않는다 — AiAnalysis.summary 주석 참고.
    @Column(name = "recommendation_reason", columnDefinition = "TEXT")
    private String recommendationReason;

    @Column(name = "draft_file_path")
    private String draftFilePath;

    // ai-api draft() 응답 원본 전체(applied/missed/unfilled/llm_hallucination 등, 필드가
    // 계속 늘어나는 중이라 컬럼을 안 쪼개고 AiAnalysis의 JSONB 컬럼들과 같은 방식으로 저장)
    @JdbcTypeCode(SqlTypes.JSON)
    @Column(name = "draft_result_json", columnDefinition = "jsonb")
    private String draftResultJson;

    // 상담원 초안생성 -> 검토요청 -> 변호사 승인/반려 흐름. DocumentReviewStatus 참고.
    @Enumerated(EnumType.STRING)
    @Column(nullable = false)
    private DocumentReviewStatus status;

    // 검토한 변호사 (검토 전엔 null)
    @ManyToOne
    @JoinColumn(name = "reviewer_id")
    private User reviewer;

    // 승인 코멘트 또는 반려 사유
    // @Lob은 쓰지 않는다 — AiAnalysis.summary 주석 참고.
    @Column(name = "review_note", columnDefinition = "TEXT")
    private String reviewNote;

    // 반려 시 변호사가 요청한 추가 자료 목록 (예: ["소득증빙", "가족관계증명서"])
    @JdbcTypeCode(SqlTypes.JSON)
    @Column(name = "requested_materials_json", columnDefinition = "jsonb")
    private String requestedMaterialsJson;

    private LocalDateTime reviewedAt;

    // 반려 후 상담원이 재제출한 횟수 (0 = 아직 재제출 없음)
    @Column(name = "revision_count", nullable = false)
    private int revisionCount;

    @CreatedDate
    @Column(nullable = false, updatable = false)
    private LocalDateTime createdAt;

    public GeneratedDocument(Consultation consultation, String formName, String recommendationReason,
                              String draftFilePath, String draftResultJson, DocumentReviewStatus status) {
        this.consultation = consultation;
        this.formName = formName;
        this.recommendationReason = recommendationReason;
        this.draftFilePath = draftFilePath;
        this.draftResultJson = draftResultJson;
        this.status = status;
        this.revisionCount = 0;
    }
}
