package com.aivle.bigproject.analysis;

import com.aivle.bigproject.analysis.dto.AiAnalysisRequest;
import com.aivle.bigproject.analysis.dto.AiAnalysisResponse;
import com.aivle.bigproject.analysis.dto.AnalysisReviewRequest;
import java.util.List;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;

@RestController
public class AiAnalysisController {

    private final AiAnalysisService aiAnalysisService;

    public AiAnalysisController(AiAnalysisService aiAnalysisService) {
        this.aiAnalysisService = aiAnalysisService;
    }

    // POST /api/consultations/{consultationId}/analyze — ai-api 분석 파이프라인을 실제로 실행하고
    // 그 결과를 새 AiAnalysis row로 저장한다. "분석 시작"/"구조대상 판정"/"누락자료 점검" 버튼이 부르는 엔드포인트.
    @PostMapping("/api/consultations/{consultationId}/analyze")
    @ResponseStatus(HttpStatus.CREATED)
    public AiAnalysisResponse analyze(@PathVariable Long consultationId) {
        return aiAnalysisService.analyze(consultationId);
    }

    // POST /api/consultations/{consultationId}/analyses — 이미 만들어진 분석 결과(위 /analyze 응답을
    // 상담원/변호사가 화면에서 수정한 버전 등)를 새 스냅샷으로 그대로 저장. ai-api를 다시 호출하지 않음.
    @PostMapping("/api/consultations/{consultationId}/analyses")
    @ResponseStatus(HttpStatus.CREATED)
    public AiAnalysisResponse create(@PathVariable Long consultationId, @RequestBody AiAnalysisRequest request) {
        return aiAnalysisService.create(consultationId, request);
    }

    // GET /api/consultations/{consultationId}/analyses — 해당 상담의 분석 결과 전체 (재분석 이력 포함)
    @GetMapping("/api/consultations/{consultationId}/analyses")
    public List<AiAnalysisResponse> findAll(@PathVariable Long consultationId) {
        return aiAnalysisService.findAllByConsultation(consultationId);
    }

    // GET /api/consultations/{consultationId}/analyses/{analysisId} — 단건 조회
    @GetMapping("/api/consultations/{consultationId}/analyses/{analysisId}")
    public AiAnalysisResponse get(@PathVariable Long consultationId, @PathVariable Long analysisId) {
        return aiAnalysisService.get(consultationId, analysisId);
    }

    // PUT /api/consultations/{consultationId}/analyses/{analysisId} — 부분 수정
    @PutMapping("/api/consultations/{consultationId}/analyses/{analysisId}")
    public AiAnalysisResponse update(@PathVariable Long consultationId, @PathVariable Long analysisId,
                                      @RequestBody AiAnalysisRequest request) {
        return aiAnalysisService.update(consultationId, analysisId, request);
    }

    // DELETE /api/consultations/{consultationId}/analyses/{analysisId}
    @DeleteMapping("/api/consultations/{consultationId}/analyses/{analysisId}")
    @ResponseStatus(HttpStatus.NO_CONTENT)
    public void delete(@PathVariable Long consultationId, @PathVariable Long analysisId) {
        aiAnalysisService.delete(consultationId, analysisId);
    }

    // POST .../analyses/{analysisId}/submit-for-review — 상담원: 확인/수정 끝났으니 검토 요청
    @PostMapping("/api/consultations/{consultationId}/analyses/{analysisId}/submit-for-review")
    public AiAnalysisResponse submitForReview(@PathVariable Long consultationId, @PathVariable Long analysisId) {
        return aiAnalysisService.submitForReview(consultationId, analysisId);
    }

    // POST .../analyses/{analysisId}/approve — 변호사 전용(SecurityConfig)
    @PostMapping("/api/consultations/{consultationId}/analyses/{analysisId}/approve")
    public AiAnalysisResponse approve(@PathVariable Long consultationId, @PathVariable Long analysisId,
                                       @RequestBody AnalysisReviewRequest request) {
        return aiAnalysisService.approve(consultationId, analysisId, request);
    }

    // POST .../analyses/{analysisId}/request-revision — 변호사 전용(SecurityConfig)
    @PostMapping("/api/consultations/{consultationId}/analyses/{analysisId}/request-revision")
    public AiAnalysisResponse requestRevision(@PathVariable Long consultationId, @PathVariable Long analysisId,
                                               @RequestBody AnalysisReviewRequest request) {
        return aiAnalysisService.requestRevision(consultationId, analysisId, request);
    }
}
