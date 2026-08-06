package com.aivle.bigproject.consultation;

import static org.assertj.core.api.Assertions.assertThat;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

// 서식 작성용 개인정보(주소·전화번호)와 그 동의 규칙 테스트. 스프링 컨텍스트도 DB도 쓰지 않는다.
//
// 여기서 확인하는 건 두 가지다.
//  - 동의 없이는 값을 갖지 않는다(화면에서도 막지만 API를 직접 부르면 지나칠 수 있다).
//  - '지금 동의가 false'와 '동의를 철회했다'를 구분한다. 이 구분이 없으면 ConsultationService가
//    상담을 저장할 때마다 ai_analysis의 사본을 지워서, 동의 화면이 미리 채워 줄 값이 사라진다.
class ConsultationPrivacyTest {

    private static final String ADDRESS = "경기도 수원시 팔달구 인계로 178 삼성아파트 302동 1104호";
    private static final String PHONE = "010-2345-6789";

    private Consultation consultation;

    @BeforeEach
    void setUp() {
        consultation = new Consultation();
    }

    private void consent() {
        consultation.applyPrivacyConsent(true, "inperson");
    }

    @Test
    @DisplayName("동의를 받으면 주소·전화번호를 보관한다")
    void keepsContactAfterConsent() {
        consent();
        consultation.applyDraftContactInfo(ADDRESS, PHONE);

        assertThat(consultation.getClientAddress()).isEqualTo(ADDRESS);
        assertThat(consultation.getClientPhone()).isEqualTo(PHONE);
        assertThat(consultation.getPrivacyConsentAt()).isNotNull();
        assertThat(consultation.getPrivacyConsentSource()).isEqualTo("inperson");
    }

    @Test
    @DisplayName("동의가 없으면 값을 보내도 보관하지 않는다")
    void dropsContactWithoutConsent() {
        consultation.applyDraftContactInfo(ADDRESS, PHONE);

        assertThat(consultation.getClientAddress()).isNull();
        assertThat(consultation.getClientPhone()).isNull();
    }

    @Test
    @DisplayName("동의를 내리면 이미 저장된 값도 함께 지운다")
    void clearsContactWhenConsentWithdrawn() {
        consent();
        consultation.applyDraftContactInfo(ADDRESS, PHONE);

        consultation.applyPrivacyConsent(false, null);
        consultation.applyDraftContactInfo(null, null);

        assertThat(consultation.getClientAddress()).isNull();
        assertThat(consultation.getClientPhone()).isNull();
        assertThat(consultation.getPrivacyConsentAt()).isNull();
        assertThat(consultation.getPrivacyConsentSource()).isNull();
    }

    @Test
    @DisplayName("동의했다가 내리면 철회로 알린다")
    void reportsRevocation() {
        consent();

        assertThat(consultation.applyPrivacyConsent(false, null)).isTrue();
    }

    @Test
    @DisplayName("동의를 받은 적이 없으면 false로 저장해도 철회가 아니다")
    void steadyFalseIsNotRevocation() {
        // 화면은 상담을 저장할 때마다 동의 필드를 함께 보낸다. 이걸 철회로 보면
        // 동의를 받기 전 단계의 저장마다 ai_analysis의 사본이 지워진다.
        assertThat(consultation.applyPrivacyConsent(false, null)).isFalse();
        assertThat(consultation.applyPrivacyConsent(null, null)).isFalse();
    }

    @Test
    @DisplayName("동의를 유지한 채 저장하면 철회가 아니다")
    void repeatedConsentIsNotRevocation() {
        consent();

        assertThat(consultation.applyPrivacyConsent(true, "inperson")).isFalse();
    }

    @Test
    @DisplayName("빈 문자열은 값이 없는 것으로 본다")
    void blankIsTreatedAsAbsent() {
        consent();
        consultation.applyDraftContactInfo("   ", "");

        assertThat(consultation.getClientAddress()).isNull();
        assertThat(consultation.getClientPhone()).isNull();
    }

    @Test
    @DisplayName("null로 보낸 항목은 기존 값을 건드리지 않는다")
    void nullLeavesExistingValue() {
        consent();
        consultation.applyDraftContactInfo(ADDRESS, PHONE);

        consultation.applyDraftContactInfo(null, "010-1111-2222");

        assertThat(consultation.getClientAddress()).isEqualTo(ADDRESS);
        assertThat(consultation.getClientPhone()).isEqualTo("010-1111-2222");
    }
}
