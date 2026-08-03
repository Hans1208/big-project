package com.aivle.bigproject.analysis.job;

import com.aivle.bigproject.analysis.AiAnalysisService;
import com.aivle.bigproject.analysis.client.ConsultAiApiClient;
import com.aivle.bigproject.analysis.client.ConsultAnalyzeApiResponse;
import com.aivle.bigproject.analysis.client.RawInputRequest;
import com.aivle.bigproject.analysis.dto.AiAnalysisResponse;
import java.util.Optional;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.scheduling.annotation.Async;
import org.springframework.stereotype.Component;
import org.springframework.transaction.event.TransactionalEventListener;

// 접수된 분석 작업을 백그라운드에서 실제로 돌린다. 요청을 처리하던 스레드는 여기 오기 전에
// 이미 202를 돌려주고 빠져나간 뒤다.
@Component
public class AnalysisJobRunner {

    private static final Logger log = LoggerFactory.getLogger(AnalysisJobRunner.class);

    private final AnalysisJobService analysisJobService;
    private final AiAnalysisService aiAnalysisService;
    private final ConsultAiApiClient aiApiClient;

    public AnalysisJobRunner(AnalysisJobService analysisJobService,
                             AiAnalysisService aiAnalysisService,
                             ConsultAiApiClient aiApiClient) {
        this.analysisJobService = analysisJobService;
        this.aiAnalysisService = aiAnalysisService;
        this.aiApiClient = aiApiClient;
    }

    // @TransactionalEventListener: 접수 트랜잭션이 커밋된 뒤에만 받는다. 안 그러면 아래에서
    //   작업 행을 id로 찾을 때 아직 DB에 없어서 못 찾을 수 있다.
    // @Async: 그 시점부터는 별도 스레드로 넘긴다. 이게 없으면 커밋 직후 요청 스레드가 그대로
    //   분석을 돌게 되어, 비동기로 바꾼 의미가 없어진다.
    @Async("analysisJobExecutor")
    @TransactionalEventListener
    public void onSubmitted(AnalysisJobSubmittedEvent event) {
        run(event.jobId());
    }

    private void run(Long jobId) {
        // 작업을 집는 데 실패하면(이미 다른 스레드가 가져갔거나 지워졌으면) 조용히 끝낸다.
        Optional<Long> claimed = analysisJobService.claim(jobId);
        if (claimed.isEmpty()) {
            log.debug("분석 작업 {}은 이미 처리 중이거나 없어 건너뜁니다", jobId);
            return;
        }
        Long consultationId = claimed.get();
        try {
            RawInputRequest request = aiAnalysisService.prepareRawInput(consultationId);
            // 여기서 몇 분이 걸린다. 이 구간만 트랜잭션 밖이라 DB 커넥션을 붙잡지 않는다.
            ConsultAnalyzeApiResponse aiResponse = aiApiClient.analyzeConsult(request);
            AiAnalysisResponse result = aiAnalysisService.buildAnalysisResponse(consultationId, aiResponse);
            analysisJobService.markSucceeded(jobId, result);
            log.info("분석 작업 {} 완료 (상담 {})", jobId, consultationId);
        } catch (Exception e) {
            // 백그라운드 스레드라 예외가 어디에도 안 나타난다. 여기서 잡아 로그로 남기고
            // 작업 상태에도 적어야 상담원 화면에 실패가 보인다.
            log.error("분석 작업 {} 실패 (상담 {})", jobId, consultationId, e);
            markFailedQuietly(jobId, e);
        }
    }

    // 실패를 기록하다가 또 실패하면(DB가 끊긴 경우 등) 그대로 두는 수밖에 없다. 다만 그
    // 예외 때문에 원래 실패 원인이 로그에서 사라지지 않도록 따로 잡아 남긴다.
    private void markFailedQuietly(Long jobId, Exception cause) {
        try {
            analysisJobService.markFailed(jobId, cause.getMessage() == null
                    ? cause.getClass().getSimpleName() : cause.getMessage());
        } catch (Exception e) {
            log.error("분석 작업 {}의 실패 기록마저 실패했습니다", jobId, e);
        }
    }
}
