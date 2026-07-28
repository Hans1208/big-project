package com.aivle.bigproject.document;

import com.aivle.bigproject.document.dto.ApproveRequest;
import com.aivle.bigproject.document.dto.GenerateDraftRequest;
import com.aivle.bigproject.document.dto.GeneratedDocumentResponse;
import com.aivle.bigproject.document.dto.RecommendFormsResponse;
import com.aivle.bigproject.document.dto.RequestRevisionRequest;
import java.util.List;
import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;

@RestController
public class GeneratedDocumentController {

    private final GeneratedDocumentService generatedDocumentService;

    public GeneratedDocumentController(GeneratedDocumentService generatedDocumentService) {
        this.generatedDocumentService = generatedDocumentService;
    }

    // POST /api/consultations/{consultationId}/analyses/{analysisId}/recommend-forms
    // ai-api에 서식 추천을 요청해서 그대로 반환 (DB 저장 안 함 — 상담원이 고르기 전)
    @PostMapping("/api/consultations/{consultationId}/analyses/{analysisId}/recommend-forms")
    public RecommendFormsResponse recommendForms(@PathVariable Long consultationId, @PathVariable Long analysisId) {
        return generatedDocumentService.recommendForms(consultationId, analysisId);
    }

    // POST /api/consultations/{consultationId}/analyses/{analysisId}/generate-draft
    // 상담원이 고른 서식으로 ai-api에 초안 생성을 요청하고, 결과를 저장
    @PostMapping("/api/consultations/{consultationId}/analyses/{analysisId}/generate-draft")
    @ResponseStatus(HttpStatus.CREATED)
    public GeneratedDocumentResponse generateDraft(@PathVariable Long consultationId, @PathVariable Long analysisId,
                                                     @RequestBody GenerateDraftRequest request) {
        return generatedDocumentService.generateDraft(consultationId, analysisId, request);
    }

    // GET /api/consultations/{consultationId}/documents — 이 상담에 생성된 초안 전체
    @GetMapping("/api/consultations/{consultationId}/documents")
    public List<GeneratedDocumentResponse> findAll(@PathVariable Long consultationId) {
        return generatedDocumentService.findAllByConsultation(consultationId);
    }

    // POST /api/consultations/{consultationId}/documents/{documentId}/submit-for-review
    // 상담원: 변호사에게 검토 요청 (반려 상태였다면 최신 분석 내용으로 초안을 다시 만들어 재제출)
    @PostMapping("/api/consultations/{consultationId}/documents/{documentId}/submit-for-review")
    public GeneratedDocumentResponse submitForReview(@PathVariable Long consultationId, @PathVariable Long documentId) {
        return generatedDocumentService.submitForReview(consultationId, documentId);
    }

    // POST /api/consultations/{consultationId}/documents/{documentId}/approve — 변호사 전용(SecurityConfig)
    @PostMapping("/api/consultations/{consultationId}/documents/{documentId}/approve")
    public GeneratedDocumentResponse approve(@PathVariable Long consultationId, @PathVariable Long documentId,
                                              @RequestBody ApproveRequest request) {
        return generatedDocumentService.approve(consultationId, documentId, request);
    }

    // POST /api/consultations/{consultationId}/documents/{documentId}/request-revision — 변호사 전용(SecurityConfig)
    @PostMapping("/api/consultations/{consultationId}/documents/{documentId}/request-revision")
    public GeneratedDocumentResponse requestRevision(@PathVariable Long consultationId, @PathVariable Long documentId,
                                                       @RequestBody RequestRevisionRequest request) {
        return generatedDocumentService.requestRevision(consultationId, documentId, request);
    }
}
