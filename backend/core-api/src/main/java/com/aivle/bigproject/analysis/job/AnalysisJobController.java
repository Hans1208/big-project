package com.aivle.bigproject.analysis.job;

import com.aivle.bigproject.analysis.job.dto.AnalysisJobResponse;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;

// AI 분석을 "맡기고 나중에 찾아가는" 방식의 입구.
//
// 기존 POST /api/consultations/{id}/analyze(AiAnalysisController)는 분석이 다 끝날 때까지
// 응답하지 않아, 상담원 화면이 몇 분씩 멈춰 있었다. 여기서는 접수만 하고 바로 응답한다.
@RestController
public class AnalysisJobController {

    private final AnalysisJobService analysisJobService;

    public AnalysisJobController(AnalysisJobService analysisJobService) {
        this.analysisJobService = analysisJobService;
    }

    // POST /api/consultations/{consultationId}/analyze-jobs — 분석 접수.
    // 실행은 백그라운드에서 일어나고, 여기서는 작업 번호만 돌려준다(202 Accepted).
    // 이미 돌고 있는 작업이 있으면 새로 만들지 않고 그 작업을 돌려준다.
    @PostMapping("/api/consultations/{consultationId}/analyze-jobs")
    @ResponseStatus(HttpStatus.ACCEPTED)
    public AnalysisJobResponse submit(@PathVariable Long consultationId) {
        return analysisJobService.submit(consultationId);
    }

    // GET /api/analysis-jobs/{jobId} — 진행 상태 조회. 화면이 주기적으로 부른다.
    // status가 SUCCEEDED가 되면 result에 분석 결과가 들어 있다.
    @GetMapping("/api/analysis-jobs/{jobId}")
    public AnalysisJobResponse get(@PathVariable Long jobId) {
        return analysisJobService.get(jobId);
    }

    // GET /api/consultations/{consultationId}/analyze-jobs/active — 아직 안 끝난 작업 조회.
    // 화면을 새로고침했을 때 돌고 있던 분석에 다시 붙기 위한 것이다. 없으면 204.
    @GetMapping("/api/consultations/{consultationId}/analyze-jobs/active")
    public ResponseEntity<AnalysisJobResponse> findActive(@PathVariable Long consultationId) {
        return analysisJobService.findActive(consultationId)
                .map(ResponseEntity::ok)
                .orElseGet(() -> ResponseEntity.noContent().build());
    }
}
