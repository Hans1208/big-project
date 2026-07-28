# AI 정의서 — agents/consult 분석 파이프라인

대상: `backend/ai-api/app/agents/consult/` 모듈, 엔드포인트 `POST /consult/analyze`.
core-api가 `POST /api/consultations/{id}/analyze`를 통해 이 파이프라인을 서버 간(backend-to-backend)으로 호출한다 (연동 방식은 [`api.md`](api.md) 참고). 프론트엔드는 이 엔드포인트를 직접 호출하지 않는다.

> ai-api에는 이 외에도 `/analysis`(Gemini, `contracts/ai_analysis_mock.json` 계약 전용), `/case-analysis`+`/eligibility/analyze`+`/missing-data/analyze`(레거시 3분리 체인, `/consult/analyze`로 통합되기 전 버전)가 남아있지만 **core-api와 연동되지 않는다.** 이 문서는 `/consult/analyze` 하나만 다룬다.

---

## 1. 개요

| 항목 | 내용 |
|---|---|
| 목적 | 상담원이 입력한 상담 텍스트 + 첨부파일(녹취록 등)을 한 번에 분석해 **사건유형 분류 · 긴급도 판단 · 법률구조 대상 여부 판단 · 누락자료 점검**을 수행 |
| 엔드포인트 | `POST /consult/analyze` (ai-api, 기본 `http://localhost:8001`) |
| 구현 | FastAPI + LangGraph, `app/agents/consult/graph.py`의 `run_consult_analysis()` |
| 호출 주체 | core-api만 (프론트 직접 호출 없음) |
| 이전 버전 | 기존에 `/case-analysis`→`/eligibility/analyze`→`/missing-data/analyze` 3개를 순서대로 호출하던 것을 그래프 하나로 통합 (커밋 `26a6dbf`) — 노드 로직 자체는 옮기기만 하고 변경 없음 |
| HITL 원칙 | 모든 응답은 "검토 대기" 성격. `relief_review_checklist.checklist_summary_for_lawyer`에 "AI 참고 자료이며 최종 확정은 조사담당변호사가 수행" 문구가 항상 포함됨. 법률구조 대상 여부(`eligible`)만 유일하게 규칙 기반으로 확정 판정하고, 나머지(승소가능성/집행가능성/구조타당성/사건유형/긴급도)는 전부 "판단을 위한 신호(signal)"이지 최종 결론이 아님 |

---

## 2. 사용 모델

| 용도 | 모델 | 비고 |
|---|---|---|
| 사건유형 분류, 긴급도 판단, 법률구조 신호 추출(5종) | OpenAI `gpt-4o-mini` (기본, env `KLAC_LLM_MODEL`로 override) | Structured Output, `method="function_calling"` |
| 누락자료 후보생성 / 검증 / 서류매핑 | env `KLAC_MISSING_DATA_MODEL` (기본값도 gpt-4o-mini 계열) | 3단계 각각 별도 LLM 호출 |
| STT (음성→텍스트) | OpenAI Whisper (로컬 실행, `WHISPER_MODEL_SIZE`로 모델 크기 조절) | 서버 기동 시 미리 로드 (`preload_models`) |
| 법률구조 대상 여부 최종 판정 | **LLM 아님 — 규칙 기반 Rule Engine** | `apply_eligibility_rules()`, 코드로 계산 (아래 5번 참고) |
| 소멸시효 계산 | **LLM 아님 — 코드 계산** | `compute_statute_of_limitations()`, `STATUTE_OF_LIMITATIONS_MAP` 참고 |

---

## 3. 요청/응답 스키마

### 요청 — `RawInput`
```json
{
  "content": {
    "summary": "string — 상담 제목/짧은 요약",
    "details": "string — 상담 본문",
    "summited_file_link": ["S3 오브젝트 key 배열 — 오타(submited 아님) 그대로 유지, core-api도 이 철자로 보냄"],
    "consult_day": "YYYY-MM-DD 또는 null"
  }
}
```
core-api 측 매핑(`AiAnalysisService.buildRawInput()`): `consultation.title`→`summary`, `consultation.inputText`→`details`, 첨부파일들의 `storage_key` 목록→`summited_file_link`, `consultation.createdAt`의 날짜부분→`consult_day`.

### 응답 — `ConsultAnalyzeResponse`
```json
{
  "raw_input": { "...요청 content 그대로..." },
  "case_analysis": { "...아래 4번..." },
  "relief_review_checklist": { "...아래 4번..." },
  "missing_items": [ "...아래 4번..." ]
}
```

---

## 4. 응답 블록 상세

### `case_analysis` (`CaseAnalysisPayload`)
```json
{
  "extracted_content": ["첨부파일에서 추출된 텍스트 목록"],
  "extracted_content_detail": [
    { "file_link": "S3 key", "status": "success|empty|unsupported|failed", "file_type": "audio|pdf|...", "error": "실패 시 사유 또는 null" }
  ],
  "case_list": [
    { "case_ratio": 0.9, "case_type": "임금체불", "case_type_reason": "3개월 동안 임금을 지급받지 못한 사례로 보임" },
    { "case_ratio": 0.1, "case_type": "기타", "case_type_reason": "..." }
  ],
  "case_emergency_ratio": 0.5,
  "case_emergency_level": "중",
  "case_emergency_reason": "..."
}
```
- `case_list`: **8개 고정 카테고리** 중 하나 이상, `case_ratio`(0~1) 내림차순. 카테고리: `임금체불`/`개인회생`/`개인파산`/`불법사금융피해`/`이혼`/`상속`/`가족관계`/`기타`. core-api는 이 중 **1순위(index 0)** 만 `AI_ANALYSIS.case_type`/`case_type_reason`으로 반영.
  - ⚠️ 이 8분류는 서식추천(forms) 기능이 쓰는 4분류(친족/상속/가사소송/가족관계등록)와 **다른 체계**이며 통합되어 있지 않음.
- `case_emergency_level`: `상`(0.7~1.0, 생명·신체 위험/시효·집행 임박) / `중`(0.3~0.7) / `하`(0~0.3) — ratio 구간과 함께 반환.

### `relief_review_checklist` (법률구조 대상 여부 4대 평가기준)
```json
{
  "eligibility": {
    "income_criterion_met": null,
    "status_criterion_met": true,
    "matched_reasons": ["국내거주 저소득 외국인근로자"],
    "required_evidence": ["소득증빙"],
    "evidence_status": "충족|미비|확인불가",
    "eligible": "대상|비대상|판단보류",
    "applied_income_threshold_ratio": null,
    "judgment_note": "판단 근거 1문장 (단정적 법률판단 표현 금지, '~로 보임' 식)"
  },
  "winnability": {
    "submitted_evidence_types": [],
    "subjective_circumstances_summary": "...",
    "statute_of_limitations_flag": "완성 명백|계산 불가|...",
    "limitation_start_date": "YYYY-MM-DD 또는 null",
    "limitation_period_years": null,
    "claim_existence_hint": "청구권 존재 언급",
    "fact_provability_hint": "입증 가능 시사",
    "extraction_confidence": "명시적|불명확",
    "review_note": "..."
  },
  "executability": {
    "debtor_asset_status": "판단 불가|...",
    "extraction_confidence": "불명확|명시적",
    "review_note": "..."
  },
  "appropriateness": {
    "case_nature": "사회적 약자 보호|...",
    "personal_motive_flags": ["감정적 분쟁"],
    "alternative_relief_mentioned": null,
    "low_value_claim_mentioned": null,
    "out_of_scope_flags": [],
    "extraction_confidence": "명시적",
    "review_note": "..."
  },
  "requires_lawyer_review": true,
  "checklist_summary_for_lawyer": "[구조대상자 여부] ... [승소가능성] ... [집행가능성] ... [구조타당성] ... ※ 위 내용은 AI 참고 자료이며, 최종 확정은 조사담당변호사가 수행합니다."
}
```
- **`eligibility.eligible`이 이 파이프라인에서 유일하게 LLM이 아닌 Rule Engine(코드)이 확정하는 값** — 나머지 3개(`winnability`/`executability`/`appropriateness`)는 LLM이 원문에서 추출한 "신호"일 뿐 결론이 아님.
- `eligible` 판정 로직(`apply_eligibility_rules()`): 소득기준(가구원수별 기준중위소득 × 1.25, 소상공인 1.50) 충족 여부 + 특수신분(기초생활수급자/장애인/범죄피해자 등) 매칭 여부를 합산해 `대상`/`비대상`/`판단보류` 중 하나로 확정, 사유별 필요증빙(`required_evidence`)도 같이 산출.
- core-api는 `eligibility.eligible`→`AI_ANALYSIS.eligibility`, 블록 전체→`AI_ANALYSIS.checklist_json`으로 저장.

### `missing_items` (누락자료 목록)
```json
[
  {
    "item": "임금 지급 내역",
    "type": "증빙|사실관계",
    "reason": "왜 필요한지",
    "confidence": 1.0,
    "evidence_check_note": "원본 재확인 근거",
    "reference_documents": [
      {
        "doc_name": "급여명세서",
        "issuing_authority": "사업주 또는 인사팀",
        "acquisition_type": "본인발급|제3자발급|절차확보",
        "acquisition_type_desc": "1문장 설명",
        "online_issuance": false,
        "online_issuance_channel": "정부24 등, 없으면 null",
        "related_law": "근거 법령, 없으면 null",
        "notes": "유의사항, 없으면 null"
      }
    ]
  }
]
```
- `confidence`(0~1) **0.7 미만인 후보는 이미 걸러져서 응답에 포함되지 않음** (`config.CONFIDENCE_THRESHOLD`).
- 항목당 참고서류 1~3개 매핑, `acquisition_type`으로 확보 난이도 구분(본인이 바로 발급 가능/제3자 요청 필요/별도 절차 필요).
- core-api는 이 배열 전체를 `AI_ANALYSIS.missing_info_json`으로 저장.

---

## 5. 파이프라인 (LangGraph, 11개 노드 순차 실행)

파일: `backend/ai-api/app/agents/consult/graph.py`

| # | 노드 | 역할 | LLM 사용 |
|---|---|---|---|
| 1 | `parse_input` | `raw_input.content`를 그래프 상태(State)로 펼침 | X |
| 2 | `process_multimodal_content` | `summited_file_link`의 각 S3 key를 다운로드해 파일 타입별 텍스트 추출 (오디오→Whisper STT, PDF/DOCX/TXT/자막 지원, **HWP/HWPX는 미지원**) | Whisper만 (LLM 아님) |
| 3 | `classify_case_type` | 사건유형 분류 (8분류, `case_ratio`+`case_type_reason`) | O |
| 4 | `classify_emergency` | 긴급도 판단 (`case_emergency_ratio`/`level`/`reason`) | O |
| 5 | `combine_case_analysis` | 3·4 결과를 `case_analysis` 블록으로 조립 | X |
| 6 | `extract_all_signals` | 법률구조 판단용 신호 5종을 **병렬**로 추출(소득·재산 언급, 특수신분 언급, 승소가능성, 집행가능성, 구조적정성) + 소멸시효 계산(코드) | O (5개 동시 호출) |
| 7 | `eligibility_rule` | **Rule Engine, LLM 미개입.** 소득기준·특수신분 매칭 결과로 `eligible` 확정 | X |
| 8 | `build_checklist` | `relief_review_checklist` 조립 (4대 기준 + 변호사용 요약문) | X |
| 9 | `candidate_generation` | 누락자료 후보 생성 | O |
| 10 | `validation` | 후보를 원문과 재대조, `confidence` 부여, 0.7 미만 제외 | O |
| 11 | `document_mapping` | 확정된 항목마다 실제 한국 서류 1~3개 매핑 | O |

그래프는 모듈 로드 시 1회 컴파일(`consult_graph = _graph_builder.compile()`), 요청마다 `consult_graph.ainvoke({"raw_input": ...})` 호출.

---

## 6. 주요 설정값 (`app/agents/consult/config.py`)

| 설정 | 값/설명 |
|---|---|
| `MEDIAN_INCOME_TABLE` | 보건복지부 2025/2026 기준중위소득, 가구원수 1~7인 |
| `INCOME_THRESHOLD_RATIO_DEFAULT` | 1.25 (기준중위소득 대비 소득 상한 배율) |
| `INCOME_THRESHOLD_RATIO_SMALL_BIZ` | 1.50 (소상공인 특례) |
| `CONFIDENCE_THRESHOLD` | 0.7 (누락자료 채택 최소 신뢰도) |
| `STATUTE_OF_LIMITATIONS_MAP` | 사건유형별 소멸시효 연수. 현재 `임금체불`=3.0, `불법사금융피해`=3.0, `기타`=10.0만 정의, **나머지는 미정(TODO)** |
| `REQUIRED_EVIDENCE_MAP` | 특수신분 사유 → 필요증빙 매핑. 코드 주석에 "팀 리뷰로 최종 확정 필요"로 명시 |

필요 환경변수(`backend/ai-api/.env`): `OPENAI_API_KEY`, `S3_BUCKET_NAME`(core-api의 `app.s3.bucket`과 반드시 동일해야 함), `AWS_REGION`, `WHISPER_MODEL_SIZE`, `KLAC_LLM_MODEL`, `KLAC_MISSING_DATA_MODEL`.

---

## 7. core-api 저장 매핑

`AiAnalysisService.analyze()` (`backend/core-api/.../analysis/AiAnalysisService.java`)가 응답을 받아 `AI_ANALYSIS` row로 변환한다. 상세 컬럼 정의는 [`data-definition.md`](data-definition.md) 참고.

| ai-api 응답 | `AI_ANALYSIS` 컬럼 |
|---|---|
| `raw_input` | `raw_input_json` |
| `case_analysis` (블록 전체) | `extracted_json` |
| `case_analysis.case_list[0].case_type` | `case_type` |
| `case_analysis.case_emergency_level` | `urgency_level` |
| `relief_review_checklist` (블록 전체) | `checklist_json` |
| `relief_review_checklist.eligibility.eligible` | `eligibility` |
| `missing_items` | `missing_info_json` |
| (core-api가 4개 값을 엮어 합성) | `summary` — 새 응답엔 단일 요약 문자열이 없어서 사건유형/사유/긴급도/구조대상여부를 한국어 문장으로 조합 |
| — | `case_subtype`/`recommendation_json`/`timeline_json`/`cluster_result_json`/`estimated_time` — 이 파이프라인은 채우지 않음(항상 NULL). 구 계약서(`contracts/ai_analysis_mock.json`) 필드로, `POST .../analyses` 원시 CRUD 쪽에서만 쓰임 |

---

## 8. 한계 / 미확정 사항

- **사건유형 8분류(agents/consult)와 서식추천 4분류(forms)가 서로 다른 체계** — 통합 안 됨. `contracts/README_ai_analysis_contract.md`에도 카테고리 목록이 아직 팀 회의 대기 중이라고 명시.
- `STATUTE_OF_LIMITATIONS_MAP`, `REQUIRED_EVIDENCE_MAP` 대부분 미정/TODO 상태.
- `CONFIDENCE_THRESHOLD`(0.7)는 실사용 데이터 기반 튜닝이 아직 안 됨.
- 첨부파일 중 **HWP/HWPX는 텍스트 추출 미지원** (별도 kordoc 파이프라인 필요, 서식 서비스 쪽에만 존재).
- 이 파이프라인은 **완전히 상태 없음(stateless)** — ai-api 자체는 DB가 없고, 결과 저장/이력관리는 전부 core-api 책임.
- `eligible`(법률구조 대상 여부)만 규칙 기반 확정이고 나머지는 전부 "참고 신호"라는 점을 화면/문서 어디서든 명확히 구분해서 표기해야 함 (법적 책임 소재상 중요).
