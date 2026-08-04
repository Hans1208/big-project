package com.aivle.bigproject.consultation;

import com.aivle.bigproject.attachment.Attachment;
import com.aivle.bigproject.user.CryptoConverter;
import com.aivle.bigproject.user.User;
import jakarta.persistence.CascadeType;
import jakarta.persistence.Column;
import jakarta.persistence.Convert;
import jakarta.persistence.Entity;
import jakarta.persistence.EntityListeners;
import jakarta.persistence.EnumType;
import jakarta.persistence.Enumerated;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.JoinColumn;
import jakarta.persistence.ManyToOne;
import jakarta.persistence.OneToMany;
import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.List;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;
import org.hibernate.annotations.JdbcTypeCode;
import org.hibernate.type.SqlTypes;
import org.springframework.data.annotation.CreatedDate;
import org.springframework.data.annotation.LastModifiedDate;
import org.springframework.data.jpa.domain.support.AuditingEntityListener;

// 상담 1건. ERD 기준 Main Table.
@Entity
@Getter
@Setter
@NoArgsConstructor
@EntityListeners(AuditingEntityListener.class)
public class Consultation {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    // 이 상담을 담당하는 상담원. 다대일(N:1) — 여러 상담이 같은 User를 가리킬 수 있음.
    // nullable=false라서 반드시 존재하는 User를 연결해야 저장 가능 (ConsultationService에서 검증함).
    @ManyToOne
    @JoinColumn(name = "user_id", nullable = false)
    private User user;

    @Column(nullable = false)
    private String title;

    // 내담자(의뢰인) 본인 이름 — User.name/email과 같은 이유로 암호화(CryptoConverter).
    // opponentName(상대방)과 헷갈리지 않도록 이름을 명확히 구분함.
    @Convert(converter = CryptoConverter.class)
    @Column(name = "client_name", nullable = false, length = 500)
    private String clientName;

    // 상담 본문(텍스트로 직접 입력했거나, STT로 변환된 내용). 녹음파일만 있는 경우 null 가능.
    // 주의: 여기에 @Lob을 붙이면 안 됨 — Postgres text 컬럼에 @Lob(String)을 쓰면 Hibernate/pgjdbc가
    // 실제 텍스트 대신 Large Object OID 참조 숫자를 저장해버리는 알려진 문제가 있음(JPA 세션 안에서는
    // 우연히 정상 조회되어 눈치채기 어렵지만, DB를 직접 SELECT하면 숫자만 보임). Postgres text는 길이
    // 제한이 없어서 애초에 @Lob이 필요 없음.
    // @Lob은 쓰지 않는다 — AiAnalysis.summary 주석 참고.
    //
    // TODO(규제): 평문으로 저장되고 있음 — 암호화 필요.
    //   상담 진술이라 주민번호·주소·가족관계가 그대로 들어간다. 정작 clientName은 암호화하면서
    //   더 민감한 이쪽이 빠져 있어 기준이 뒤집혀 있다.
    //   @Convert(converter = CryptoConverter.class) 한 줄이면 되지만, 이미 저장된 평문 행은
    //   복호화가 깨진다. 팀원 각자의 로컬 DB를 함께 초기화해야 하므로 합의 후 적용할 것.
    @Column(name = "input_text", columnDefinition = "TEXT")
    private String inputText;

    // "상담 저장" 버튼을 누를 때마다의 채널별 input_text 스냅샷 보관용(감사/이력 목적). 매 저장마다
    // 하나씩 쌓이기만 하고 지우지 않음 — ConsultationService.saveTranscript() 참고. "분석 내용
    // 저장"(AiAnalysisService)은 ai_analysis 테이블만 건드리고 여기는 건드리지 않는다.
    // 전화상담(call_*)과 대면상담(inperson_*)을 분리한 이유: 두 채널의 실시간 상담 메모/STT 결과가
    // 화면에서 섞여 보이면 안 된다는 요구에 맞춰, 저장되는 이력도 채널별로 나눈다.
    // 이전에 있던 단일 input_texts/input_texts_masked 컬럼을 대체한다(더 이상 관리 안 함 — DB에
    // 남아 있어도 ddl-auto: update는 안 쓰는 컬럼을 지우지 않으므로 그냥 방치됨).
    //
    // DB엔 이미 행이 있던(NULL) 상태로 컬럼이 추가될 수 있어 getter에서 항상 non-null을 보장하지
    // 않는다. null-safe 추가는 addCallInputText() 등 아래 헬퍼로만 한다.
    @JdbcTypeCode(SqlTypes.ARRAY)
    @Column(name = "call_input_texts", columnDefinition = "text[]")
    private List<String> callInputTexts = new ArrayList<>();

    @JdbcTypeCode(SqlTypes.ARRAY)
    @Column(name = "call_input_texts_masked", columnDefinition = "text[]")
    private List<String> callInputTextsMasked = new ArrayList<>();

    @JdbcTypeCode(SqlTypes.ARRAY)
    @Column(name = "inperson_input_texts", columnDefinition = "text[]")
    private List<String> inpersonInputTexts = new ArrayList<>();

    // 마스킹은 지금 대면 상담(mic-stt-mask) 세션에서만 실제로 일어난다 — 전화상담은 아직 자동 STT가
    // 없어 call_input_texts_masked는 사실상 계속 비어 있을 수 있다.
    @JdbcTypeCode(SqlTypes.ARRAY)
    @Column(name = "inperson_input_texts_masked", columnDefinition = "text[]")
    private List<String> inpersonInputTextsMasked = new ArrayList<>();

    public void addCallInputText(String value) {
        addTo(() -> this.callInputTexts, list -> this.callInputTexts = list, value);
    }

    public void addCallInputTextMasked(String value) {
        addTo(() -> this.callInputTextsMasked, list -> this.callInputTextsMasked = list, value);
    }

    public void addInpersonInputText(String value) {
        addTo(() -> this.inpersonInputTexts, list -> this.inpersonInputTexts = list, value);
    }

    public void addInpersonInputTextMasked(String value) {
        addTo(() -> this.inpersonInputTextsMasked, list -> this.inpersonInputTextsMasked = list, value);
    }

    private void addTo(java.util.function.Supplier<List<String>> getter,
                        java.util.function.Consumer<List<String>> setter, String value) {
        if (value == null || value.isBlank()) {
            return;
        }
        List<String> list = getter.get();
        if (list == null) {
            list = new ArrayList<>();
            setter.accept(list);
        }
        list.add(value);
    }

    // 상대방 이름 — 유사 사건 집단화(clustering)에 참고용으로 쓰일 필드 (ERD 주석 기준)
    @Column(name = "opponent_name")
    private String opponentName;

    @Enumerated(EnumType.STRING)
    @Column(nullable = false)
    private ConsultationStatus status = ConsultationStatus.RECEIVED;

    // 사건 대분류/소분류 (등록 화면 ChoicePicker 선택값). 분류 체계가 아직 팀 협의 중이라
    // AiAnalysis.caseType과 마찬가지로 enum이 아닌 자유 문자열로 둠.
    @Column(name = "category")
    private String category;

    @Column(name = "type")
    private String type;

    // 법률구조 대상자 유형 (예: basicLivelihood, nearPoverty, none 등 — frontend legalAidApplicantTypes 참고)
    @Column(name = "legal_aid_type")
    private String legalAidType;

    @Column(name = "eligibility_evidence_submitted")
    private Boolean eligibilityEvidenceSubmitted = false;

    // 이 상담에 딸린 첨부파일 목록. 1:N 관계.
    // cascade=ALL: Consultation을 저장/삭제하면 Attachment도 같이 저장/삭제됨
    // orphanRemoval=true: 이 리스트에서 Attachment를 빼면 DB에서도 자동 삭제됨
    // 기본적으로 LAZY 로딩이라, 트랜잭션이 열려있을 때만 접근 가능 (Service 계층 안에서 다뤄야 함)
    @OneToMany(mappedBy = "consultation", cascade = CascadeType.ALL, orphanRemoval = true)
    private List<Attachment> attachments = new ArrayList<>();

    @CreatedDate
    @Column(nullable = false, updatable = false)
    private LocalDateTime createdAt;

    @LastModifiedDate
    @Column(nullable = false)
    private LocalDateTime updatedAt;

    // 생성 시 필요한 필드만 받는 생성자
    public Consultation(User user, String title, String clientName, String inputText, String opponentName,
                         String category, String type, String legalAidType, Boolean eligibilityEvidenceSubmitted) {
        this.user = user;
        this.title = title;
        this.clientName = clientName;
        this.inputText = inputText;
        this.opponentName = opponentName;
        this.category = category;
        this.type = type;
        this.legalAidType = legalAidType;
        this.eligibilityEvidenceSubmitted = eligibilityEvidenceSubmitted != null && eligibilityEvidenceSubmitted;
    }
}
