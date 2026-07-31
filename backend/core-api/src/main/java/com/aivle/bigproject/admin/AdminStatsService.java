package com.aivle.bigproject.admin;

import com.aivle.bigproject.admin.dto.AdminStatsResponse;
import com.aivle.bigproject.admin.dto.AdminStatsResponse.AnalysisStatusBreakdown;
import com.aivle.bigproject.analysis.AiAnalysisRepository;
import com.aivle.bigproject.analysis.AnalysisReviewStatus;
import com.aivle.bigproject.consultation.ConsultationRepository;
import com.aivle.bigproject.user.ApprovalStatus;
import com.aivle.bigproject.user.UserRepository;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
@Transactional(readOnly = true)
public class AdminStatsService {

    private final ConsultationRepository consultationRepository;
    private final UserRepository userRepository;
    private final AiAnalysisRepository aiAnalysisRepository;

    public AdminStatsService(ConsultationRepository consultationRepository,
                              UserRepository userRepository,
                              AiAnalysisRepository aiAnalysisRepository) {
        this.consultationRepository = consultationRepository;
        this.userRepository = userRepository;
        this.aiAnalysisRepository = aiAnalysisRepository;
    }

    public AdminStatsResponse getStats() {
        long totalConsultations = consultationRepository.count();
        long activeUsers = userRepository.countByApprovalStatus(ApprovalStatus.APPROVED);
        long pendingUserApprovals = userRepository.countByApprovalStatus(ApprovalStatus.PENDING);

        // 분석 행 전체가 아니라 '상담별 최신 분석 1건'만 센다.
        //
        // 예전에는 countByStatus로 전 행을 셌다. 같은 상담을 다시 분석하면 행이 하나 더 생기는
        // 구조라(analyze()에서 함께 고쳤다), 재분석을 할수록 분모가 커져 처리율이 떨어졌다.
        // 실제로 상담 17건에 분석이 19건 있었고 그중 14건이 같은 상담의 중복이었다.
        // 지표가 뜻하는 바("검토가 끝난 상담의 비율")에 맞추려면 상담 하나를 한 번만 세야 한다.
        //
        // analyze()를 고쳐도 이미 쌓인 중복 행은 그대로 남아 있으므로, 집계 쪽에서도 막아둔다.
        // 검토를 실제로 거친 건만 '처리 완료'로 센다.
        // approve()/requestRevision()는 항상 reviewedAt을 남기므로, 그게 비어 있는 APPROVED는
        // 검토 이력 없이 상태만 들어간 행이다(개발 중 만들어진 테스트 데이터). 그런 행까지
        // 분자에 넣으면 아무도 승인하지 않았는데 처리율이 올라가 있게 된다.
        // 상담 하나당 한 건만 센다. 그 한 건은 '검토를 받은 행이 있으면 그중 최신'이고,
        // 없으면 '전체 중 최신'이다.
        //
        // 단순히 최신 행만 보면 두 가지가 어긋난다.
        //   - 같은 상담을 여러 번 분석하면 그 횟수만큼 분모가 커진다 (재분석할수록 처리율 하락)
        //   - 승인받은 뒤 다시 분석하면 더 새로운 초안이 생겨 승인 이력이 가려진다
        // 실제로 상담 30은 id=30이 승인됐는데 id=33(재분석)이 최신이라 '검토 전'으로 잡혔다.
        //
        // 검토 여부는 status가 아니라 reviewedAt으로 판단한다. approve()/requestRevision()는
        // 항상 reviewedAt을 남기므로, 그게 비어 있는 APPROVED는 개발 중 상태만 바꿔둔 행이다.
        Map<Long, Object[]> pickedPerConsultation = new LinkedHashMap<>();
        for (Object[] row : aiAnalysisRepository.findAllForStats()) {
            Long consultationId = (Long) row[0];
            Object[] current = pickedPerConsultation.get(consultationId);
            // 쿼리가 id 오름차순이라 나중에 오는 행이 항상 더 최신이다.
            // 이미 '검토된 행'을 골라뒀다면, 검토되지 않은 새 행으로 덮어쓰지 않는다.
            boolean currentReviewed = current != null && current[2] != null;
            boolean rowReviewed = row[2] != null;
            if (current == null || rowReviewed || !currentReviewed) {
                pickedPerConsultation.put(consultationId, row);
            }
        }

        long approved = 0;
        long rejected = 0;
        long pending = 0;
        for (Object[] row : pickedPerConsultation.values()) {
            AnalysisReviewStatus status = (AnalysisReviewStatus) row[1];
            boolean reviewed = row[2] != null;
            if (reviewed && status == AnalysisReviewStatus.APPROVED) {
                approved++;
            } else if (reviewed && status == AnalysisReviewStatus.REVISION_REQUESTED) {
                rejected++;
            } else {
                pending++;
            }
        }
        long totalAnalyses = approved + rejected + pending;

        double analysisProcessingRate = totalAnalyses == 0
                ? 0.0
                : (double) (approved + rejected) / totalAnalyses;

        Map<String, Long> caseTypeStats = new LinkedHashMap<>();
        for (Object[] row : aiAnalysisRepository.countGroupedByCaseType()) {
            caseTypeStats.put((String) row[0], (Long) row[1]);
        }

        return new AdminStatsResponse(
                totalConsultations,
                activeUsers,
                analysisProcessingRate,
                pendingUserApprovals,
                caseTypeStats,
                new AnalysisStatusBreakdown(approved, rejected, pending)
        );
    }
}
