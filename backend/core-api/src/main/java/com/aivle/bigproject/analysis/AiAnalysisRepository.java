package com.aivle.bigproject.analysis;

import java.util.List;
import java.util.Optional;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;

public interface AiAnalysisRepository extends JpaRepository<AiAnalysis, Long> {

    // 메서드 이름만으로 Spring Data가 "consultation.id로 조회"하는 쿼리를 자동 생성함 (JPQL 직접 안 씀)
    List<AiAnalysis> findByConsultationId(Long consultationId);

    // 상담이 삭제될 때 딸린 분석 결과도 같이 지우기 위해 사용 (ConsultationService.delete 참고)
    void deleteByConsultationId(Long consultationId);

    // 관리자 대시보드 "분석 처리 현황"(승인/반려/대기) 집계용 (AdminStatsService)
    long countByStatus(AnalysisReviewStatus status);

    // 한 상담의 가장 최근 분석 1건. analyze()가 검토 전 초안을 덮어쓸 대상을 찾을 때 쓴다.
    Optional<AiAnalysis> findFirstByConsultationIdOrderByIdDesc(Long consultationId);

    // 상담별 '최신 분석 1건'의 (상태, 검토여부)를 모은다 (AdminStatsService 처리율 집계용).
    //
    // 전체 행을 세면 같은 상담을 여러 번 분석했을 때 그 횟수만큼 분모가 커진다.
    // 재분석을 할수록 처리율이 떨어지는 셈이라 지표로 쓸 수 없다.
    // 상담 하나당 한 건만 세도록 각 상담의 최대 id(=가장 최근 행)만 남긴다.
    //
    // reviewedAt도 함께 가져오는 이유: 개발 중 만들어진 데이터 중에 검토를 거치지 않고
    // 상태만 APPROVED로 들어간 행이 있다(검토자·검토일·검토의견이 전부 비어 있음).
    // approve()/requestRevision()는 반드시 reviewedAt을 남기므로, 그게 없는 APPROVED는
    // 실제 검토 이력이 아니다. 그런 행을 분자에 넣으면 아무도 승인하지 않았는데
    // 처리율이 올라가 있는 상태가 된다.
    // '최신 행'만 보면 안 되는 이유가 하나 더 있다. 검토를 받은 뒤 같은 상담을 다시 분석하면
    // 더 새로운 DRAFTED 행이 생겨, 이미 승인된 분석이 그 뒤에 가려진다. 실제로 상담 30에서
    // id=30이 승인됐는데 id=33(재분석)이 최신이라 집계에는 '검토 전'으로 잡혔다.
    //
    // 그래서 상담 단위로 (검토된 행이 있으면 그중 최신, 없으면 전체 중 최신)을 고른다.
    // 아래는 그 판단에 필요한 것만 상담별로 모아온다: 상담 id, 상태, 검토일.
    @Query("""
            SELECT a.consultation.id, a.status, a.reviewedAt FROM AiAnalysis a
            ORDER BY a.consultation.id, a.id
            """)
    List<Object[]> findAllForStats();

    // 관리자 대시보드 "사건 유형별 상담 통계"용. case_type은 자유 문자열이라 enum 그룹핑이
    // 아니라 값 자체로 그룹핑함 — null인 건(아직 분류 전) 통계에서 제외.
    // 처리율과 같은 이유로 여기서도 상담별 1건만 센다. 전 행을 세면 같은 상담을 여섯 번
    // 분석했을 때 그 사건 유형이 여섯 건으로 잡혀 유형별 분포가 왜곡된다.
    // 사건유형은 재분석해도 거의 바뀌지 않으므로 여기서는 최신 행 기준으로 충분하다.
    @Query("""
            SELECT a.caseType, COUNT(a) FROM AiAnalysis a
            WHERE a.caseType IS NOT NULL
              AND a.id IN (SELECT MAX(b.id) FROM AiAnalysis b GROUP BY b.consultation.id)
            GROUP BY a.caseType
            """)
    List<Object[]> countGroupedByCaseType();
}
