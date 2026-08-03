package com.aivle.bigproject.analysis.job;

import java.util.Collection;
import java.util.Optional;
import org.springframework.data.jpa.repository.JpaRepository;

public interface AnalysisJobRepository extends JpaRepository<AnalysisJob, Long> {

    // 아직 안 끝난 작업이 있는지 확인용(PENDING/RUNNING). 같은 상담에 분석을 두 번 걸지 않기 위해,
    // 그리고 새로고침한 화면이 진행 중이던 작업을 다시 찾아 붙기 위해 쓴다.
    Optional<AnalysisJob> findFirstByConsultationIdAndStatusInOrderByIdDesc(
            Long consultationId, Collection<AnalysisJobStatus> statuses);

    // 상담이 삭제될 때 딸린 작업도 같이 지운다. Consultation이 이 목록을 들고 있지 않은
    // 단방향 FK라 cascade가 걸리지 않는다(AiAnalysis/GeneratedDocument와 같은 사정).
    void deleteByConsultationId(Long consultationId);
}
