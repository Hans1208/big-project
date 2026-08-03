package com.aivle.bigproject.analysis.job;

import com.aivle.bigproject.consultation.Consultation;
import com.aivle.bigproject.consultation.ConsultationStatus;
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
import org.springframework.data.annotation.CreatedDate;
import org.springframework.data.jpa.domain.support.AuditingEntityListener;

// AI 분석 실행 한 건. "분석 시작"을 누른 시점에 만들어지고, 백그라운드에서 ai-api 호출이
// 끝나면 결과나 실패 사유가 여기 채워진다.
//
// 이 테이블을 두는 이유는 두 가지다.
//   1. 분석은 몇 분씩 걸린다. 요청을 붙잡고 기다리면 상담원 화면이 그동안 멈춰 있고,
//      로드밸런서를 거치는 순간 응답을 기다리다 연결이 끊긴다.
//   2. 진행 상태를 메모리에만 두면 서버가 재시작될 때 통째로 사라진다. 그러면 화면은
//      끝나지 않는 "분석 중"에 갇힌다.
@Entity
@Table(name = "analysis_job")
@Getter
@Setter
@NoArgsConstructor
@EntityListeners(AuditingEntityListener.class)
public class AnalysisJob {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @ManyToOne
    @JoinColumn(name = "consultation_id", nullable = false)
    private Consultation consultation;

    @Enumerated(EnumType.STRING)
    @Column(nullable = false)
    private AnalysisJobStatus status = AnalysisJobStatus.PENDING;

    // 분석을 시작하기 직전의 상담 상태. 분석이 실패하면 여기로 되돌린다.
    //
    // 동기 방식일 때는 실패하면 트랜잭션이 통째로 롤백되면서 "분석 중"도 같이 사라졌다.
    // 비동기에서는 화면에 진행 상황을 보여주려고 "분석 중"을 먼저 커밋하기 때문에,
    // 실패했을 때 직접 되돌리지 않으면 그 상담은 영원히 "분석 중"으로 남는다.
    @Enumerated(EnumType.STRING)
    @Column(name = "previous_consultation_status")
    private ConsultationStatus previousConsultationStatus;

    // 완성된 분석 결과(AiAnalysisResponse를 그대로 직렬화한 JSON).
    //
    // ai_analysis 테이블이 아니라 여기에 담는다. analyze()는 DB에 분석 행을 만들지 않는다는
    // 규칙을 지키기 위해서다(AiAnalysisService.analyze() 주석 참고) — 상담원이 화면에서 결과를
    // 확인하고 "분석 내용 저장"을 눌러야 비로소 ai_analysis 행이 생긴다. 비동기로 바뀌었다고
    // 결과를 미리 저장해 버리면, 상담원이 보지도 않은 AI 값이 저장된 분석인 것처럼 남는다.
    @Column(name = "result_json", columnDefinition = "TEXT")
    private String resultJson;

    @Column(name = "error_message", columnDefinition = "TEXT")
    private String errorMessage;

    // 이 작업을 요청한 사람. 감사 로그에도 실행자가 남지만(AsyncConfig 참고), 작업 행 자체에도
    // 남겨 둔다 — 새로고침 후 화면을 복구할 때와 실패 원인을 되짚을 때 쓴다.
    @Column(name = "requested_by_email")
    private String requestedByEmail;

    @CreatedDate
    @Column(name = "created_at", updatable = false)
    private LocalDateTime createdAt;

    @Column(name = "started_at")
    private LocalDateTime startedAt;

    @Column(name = "finished_at")
    private LocalDateTime finishedAt;

    public AnalysisJob(Consultation consultation, String requestedByEmail) {
        this.consultation = consultation;
        this.requestedByEmail = requestedByEmail;
        this.status = AnalysisJobStatus.PENDING;
    }

    // 화면이 폴링을 멈춰도 되는 시점.
    public boolean isFinished() {
        return status == AnalysisJobStatus.SUCCEEDED || status == AnalysisJobStatus.FAILED;
    }
}
