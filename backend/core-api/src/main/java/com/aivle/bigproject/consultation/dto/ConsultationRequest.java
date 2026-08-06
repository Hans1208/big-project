package com.aivle.bigproject.consultation.dto;

import com.aivle.bigproject.consultation.ConsultationStatus;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import java.util.List;

// 생성(POST)과 수정(PUT) 요청에 공통으로 쓰는 DTO.
// 수정 시엔 null이 아닌 필드만 반영됨 (ConsultationService.update 참고) — 즉 "부분 수정" 방식.
// 생성 시엔 status를 보내도 무시되고 항상 RECEIVED로 시작함 (ConsultationService.create 참고).
// attachments는 생성(POST) 시에만 반영됨 — PUT(update)은 이 필드를 무시함. 이미 있는 상담에 자료를
// "추가"할 때는 AttachmentController의 POST .../attachments/register를, "삭제"할 때는
// DELETE .../attachments/{attachmentId}를 대신 쓴다(둘 다 attachmentService가 처리).
//
// @NotNull/@NotBlank는 ConsultationController.create()에서만 @Valid로 발동시킨다 — update()는
// 부분 수정이라 필드가 비어있는 게 정상이라서 같은 DTO를 검증 없이 그대로 쓴다.
public record ConsultationRequest(
        @NotNull(message = "userId는 필수입니다") Long userId,
        @NotBlank(message = "title은 필수입니다") String title,
        @NotBlank(message = "clientName은 필수입니다") String clientName,
        String inputText,
        String opponentName,
        ConsultationStatus status,
        String category,
        String type,
        String legalAidType,
        Boolean eligibilityEvidenceSubmitted,
        // 서식 작성용 개인정보. 법원 서식의 당사자 주소는 송달을 위한 법정 필수
        // 기재사항이라 이게 없으면 초안이 성립하지 않는다.
        //
        // 이 셋은 세트로 움직인다 — 동의가 없으면 주소·전화번호는 저장되지 않는다
        // (Consultation.applyDraftContactInfo). 화면에서도 막지만 이 API를 직접
        // 부르면 그 검사를 지나칠 수 있어 서버에서도 본다.
        String clientAddress,
        String clientPhone,
        Boolean privacyConsent,
        // 어느 채널에서 받은 동의인지(call / inperson). 개인정보 보호법 시행령
        // 제17조가 인정하는 동의 방법이 채널마다 달라, 나중에 입증할 때 필요하다.
        String privacyConsentSource,
        List<AttachmentRegistration> attachments
) {
    // 프론트가 S3에 직접 올린 뒤, "어디에 올렸는지"만 상담 생성 시 같이 넘기는 첨부파일 메타데이터.
    // fileKey가 비어있으면(S3 업로드 실패로 로컬 폴백된 항목) 서버에 등록할 실체가 없으므로 무시함.
    public record AttachmentRegistration(String fileName, String fileType, String fileKey, String fileUrl, String contentType) {}
}
