# core-api REST API

Base URL: `http://localhost:8080`

현재 구현된 범위: **User / Consultation / Attachment / AI_ANALYSIS** CRUD + **agents/consult AI 분석 연동**.
core-api가 ai-api(`POST /consult/analyze`)를 서버 간(backend-to-backend)으로 직접 호출해서 실제 AI 분석을
수행하고 결과를 `AI_ANALYSIS`에 저장한다 (`POST /api/consultations/{id}/analyze` 참고). 첨부파일은 S3에
저장되며, 브라우저가 presigned URL로 S3에 직접 업로드한다 (`POST /api/attachments/presigned-upload` 참고).

`AI_ANALYSIS`는 `contracts/ai_analysis_mock.json` 계약서 필드명과 1:1로 맞춰서 구현했으나,
`case_type` 카테고리 목록·`urgency_level`/`eligibility` 값 표기·`checklist_json` 항목은
아직 팀 회의로 확정 전이라 자유 문자열/JSON으로 열어둔 상태 (값이 나중에 바뀔 수 있음).
인증(로그인/비밀번호)은 아직 미구현.

모든 요청/응답 Body는 `application/json` (파일 업로드/presigned-upload 요청만 예외 — 아래 각 섹션 참고).

상세 테이블 정의는 [`data-definition.md`](data-definition.md), ERD는 [`erd.drawio`](erd.drawio),
ai-api 연동 파이프라인 자체(모델/프롬프트/판단 로직)는 [`ai-definition.md`](ai-definition.md) 참고.

---

## 공통 에러 응답

리소스가 없으면(`NotFoundException`) `GlobalExceptionHandler`(`common/exception/`)가 아래 형식으로 404를 내려줍니다.
(User/Consultation/Attachment/AiAnalysis 서비스가 각자 예외를 던지던 걸 여기 한 곳으로 모음)

```json
{
  "timestamp": "2026-07-20T05:00:18.393Z",
  "status": 404,
  "error": "Not Found",
  "message": "상담을 찾을 수 없습니다: 999",
  "path": "/api/consultations/999"
}
```

| status | 상황 |
|---|---|
| 400 | 요청 body 파싱 실패 (JSON 형식 오류 등) |
| 404 | 경로의 id에 해당하는 리소스 없음 |
| 405 | 해당 경로에 정의되지 않은 HTTP 메서드 호출 |

---

## User (`/api/users`)

상담원 계정. `Consultation`이 참조하는 최소 범위만 구현 — 수정/삭제, 비밀번호/인증은 아직 없음.

### POST /api/users
상담원 생성.

Request
```json
{
  "name": "김상담",
  "role": "CONSULTANT",
  "email": "consultant1@example.com"
}
```
- `role`: `"CONSULTANT"`(상담원) | `"LAWYER"`(변호사) | `"ADMIN"`(관리자)

Response `201`
```json
{
  "id": 1,
  "name": "김상담",
  "role": "CONSULTANT",
  "email": "consultant1@example.com",
  "createdAt": "2026-07-20T13:55:25.338075",
  "updatedAt": "2026-07-20T13:55:25.338075"
}
```

### GET /api/users
전체 목록. Response `200` — `UserResponse[]`

### GET /api/users/{id}
단건 조회. Response `200` — `UserResponse`, 없으면 `404`

---

## Consultation (`/api/consultations`)

상담 1건. `userId`로 `User`를 반드시 참조.

### POST /api/consultations
Request
```json
{
  "userId": 1,
  "title": "임금체불 상담",
  "inputText": "3개월치 임금을 못 받았습니다",
  "opponentName": "OO상사",
  "category": "친족",
  "type": "약혼",
  "legalAidType": "wageArrears",
  "eligibilityEvidenceSubmitted": false,
  "attachments": [
    {
      "fileName": "rec.mp3",
      "fileType": "녹취록",
      "fileKey": "consult-attachments/2dcabc92-...__rec.mp3",
      "fileUrl": "https://aivle-test-ai-34178924.s3.ap-northeast-2.amazonaws.com/consult-attachments/2dcabc92-...__rec.mp3",
      "contentType": "audio/mpeg"
    }
  ]
}
```
- `userId`: 필수, 존재하지 않으면 `404`
- `title`: 필수
- `inputText`: 선택 (녹음파일만 있고 텍스트 없는 상담 가능)
- `opponentName`, `category`, `type`, `legalAidType`, `eligibilityEvidenceSubmitted`: 선택 (자유 문자열/불리언, 값 목록은 [`data-definition.md`](data-definition.md) 참고)
- `attachments`: 선택. 브라우저가 `POST /api/attachments/presigned-upload`로 미리 S3에 올린 파일들의 메타데이터를 여기서 한 번에 등록. **`fileKey`가 없는 항목(= S3 업로드가 안 되고 로컬에만 남은 항목)은 무시됨** — 서버에 실체가 없는 파일을 등록해봐야 다운로드/AI분석 둘 다 불가능하기 때문
- `status`는 생성 시 무시되고 항상 `RECEIVED`로 시작

Response `201` — `ConsultationResponse` (아래 GET 참고)

### GET /api/consultations
전체 목록, 각 항목에 `attachments` 포함. Response `200` — `ConsultationResponse[]`

### GET /api/consultations/{id}
단건 조회. 없으면 `404`.

Response `200`
```json
{
  "id": 1,
  "userId": 1,
  "title": "임금체불 상담",
  "inputText": "3개월치 임금을 못 받았습니다",
  "opponentName": "OO상사",
  "status": "RECEIVED",
  "category": "친족",
  "type": "약혼",
  "legalAidType": "wageArrears",
  "eligibilityEvidenceSubmitted": false,
  "createdAt": "2026-07-20T13:55:25.651",
  "updatedAt": "2026-07-20T13:55:25.651",
  "attachments": [
    {
      "id": 1,
      "fileName": "rec.mp3",
      "fileType": "녹취록",
      "extractedText": null,
      "uploadedAt": "2026-07-20T13:55:36.486",
      "downloadUrl": "/api/consultations/1/attachments/1"
    }
  ]
}
```
(응답에는 S3 `storage_key`/`storage_bucket`은 노출되지 않음 — 다운로드는 항상 `downloadUrl`을 통해서만)

### PUT /api/consultations/{id}
부분 수정 — body에 넣은 필드만 갱신됨 (넣지 않은 필드는 유지).

Request (예: 상태만 변경)
```json
{ "status": "ANALYZING" }
```
- `status`: `"RECEIVED"` | `"ANALYZING"` | `"COMPLETED"`
- `title`, `inputText`, `opponentName`, `category`, `type`, `legalAidType`, `eligibilityEvidenceSubmitted`도 같은 방식으로 부분 갱신 가능
- `userId`는 이 엔드포인트로 변경 불가 (상담 담당자 재배정은 아직 미구현)
- `attachments`는 이 엔드포인트로 갱신 불가 (첨부파일은 생성 시에만 등록됨)

Response `200` — `ConsultationResponse`, 없으면 `404`

### DELETE /api/consultations/{id}
상담 삭제. 딸린 `Attachment`(S3 오브젝트 포함)와 `AI_ANALYSIS`도 함께 삭제됨 (cascade). Response `204`

---

## Attachment

상담 1건에 여러 개 첨부 가능 (녹취록, 신분증, 증빙자료 등). 실제 파일은 S3에 저장됨.
업로드 경로는 두 가지:
1. **브라우저 직접 업로드(기본, 프론트가 사용하는 방식)**: `POST /api/attachments/presigned-upload`로 presigned URL을 받아 브라우저가 S3에 직접 PUT → 상담 생성/수정 시 `fileKey`만 core-api에 등록 (위 `POST /api/consultations` 참고). 파일 바이트가 core-api를 거치지 않아 서버 부하가 없음.
2. **서버 경유 업로드(대안)**: `POST /api/consultations/{consultationId}/attachments`로 멀티파트 전송 → core-api가 받아서 S3에 대신 업로드.

### POST /api/attachments/presigned-upload
브라우저가 S3에 직접 PUT할 수 있는 임시 업로드 URL을 발급 (DB에는 아무것도 기록하지 않음 — 등록은 상담 생성 시 `fileKey`로 별도 처리).

Request
```json
{ "fileName": "rec.mp3", "contentType": "audio/mpeg", "fileType": "녹취록" }
```

Response `200`
```json
{
  "uploadUrl": "https://aivle-test-ai-34178924.s3.ap-northeast-2.amazonaws.com/consult-attachments/...?X-Amz-Algorithm=...",
  "fileKey": "consult-attachments/2dcabc92-...__rec.mp3",
  "fileUrl": "https://aivle-test-ai-34178924.s3.ap-northeast-2.amazonaws.com/consult-attachments/2dcabc92-...__rec.mp3"
}
```
- `uploadUrl`: 15분간 유효한 presigned PUT URL. 브라우저가 이 URL로 파일 바이트를 직접 `PUT` (요청 시 사용한 `contentType`과 동일한 `Content-Type` 헤더 필요)
- ⚠️ S3 버킷에 프론트 오리진의 `PUT`을 허용하는 CORS 설정이 돼 있어야 브라우저가 실제로 PUT 가능 (AWS 콘솔에서 별도 설정, 코드와 무관)

### POST /api/consultations/{consultationId}/attachments
`multipart/form-data` — 서버 경유 업로드
- `file`: 업로드할 파일
- `fileType`: 자유 문자열 (예: `"녹취록"`, `"신분증"`, `"증빙자료"` — 고정 enum 아님)

Response `201`
```json
{
  "id": 1,
  "fileName": "rec.mp3",
  "fileType": "녹취록",
  "extractedText": null,
  "uploadedAt": "2026-07-20T13:55:36.486",
  "downloadUrl": "/api/consultations/1/attachments/1"
}
```
- `extractedText`: STT/OCR 결과. 지금은 채우는 로직이 없어 항상 `null` (ai-api STT 결과를 여기로 역주입하는 파이프라인은 아직 없음 — 현재는 `AI_ANALYSIS.extracted_json` 쪽에만 반영됨)

### GET /api/consultations/{consultationId}/attachments/{attachmentId}
파일 원본 다운로드 (`Content-Disposition: attachment`, S3에서 스트리밍). 없으면 `404`.

### DELETE /api/consultations/{consultationId}/attachments/{attachmentId}
첨부파일 삭제 — DB row와 S3 오브젝트 모두 제거. Response `204`

---

## AI_ANALYSIS

`contracts/ai_analysis_mock.json` 계약서 필드명과 **1:1로 매칭**됨 (요청/응답 JSON은 snake_case).
상담 1건에 여러 번 재분석이 가능하다고 보고 1:N으로 설계함 (재분석 이력 보존).

⚠️ **주의**: `case_type` 카테고리 목록, `urgency_level`/`eligibility` 값 표기, `checklist_json` 항목은
아직 팀 회의로 확정 전이라 자유 문자열/JSON으로 열어둔 상태. 확정되면 값이 바뀔 수 있음.
`case_subtype`은 계약서 v0.1엔 없던 필드로, `case_type` 세부유형 용도로 추가 결정됨.

엔드포인트는 두 가지 역할로 나뉜다:
- **`POST .../analyze`**: core-api가 ai-api를 실제로 호출해서 새로 분석하고 저장 (요청 body 없음)
- **`POST .../analyses`**: 이미 갖고 있는 분석 결과(예: `/analyze` 응답을 상담원/변호사가 화면에서 수정한 버전)를 그대로 새 스냅샷으로 저장 — ai-api를 다시 호출하지 않음

### POST /api/consultations/{consultationId}/analyze
**agents/consult 실제 분석 트리거.** core-api가 해당 상담의 `title`/`inputText`/첨부파일(S3 key 목록)로
ai-api `POST /consult/analyze`를 서버 간(backend-to-backend)으로 호출하고, 그 결과를 새 `AI_ANALYSIS` row로
저장한다. 상담 화면의 "분석 시작"/"구조대상 판정"/"누락자료 점검" 버튼이 이 엔드포인트를 호출한다.
파이프라인 상세(모델/판단 로직)는 [`ai-definition.md`](ai-definition.md) 참고.

Request: 없음 (body 불필요)

동작 중 `consultation.status`가 `RECEIVED`→`ANALYZING`→`COMPLETED`로 전이됨.

Response `201` — 아래 `POST .../analyses` 응답과 같은 형태, 단 실제 AI 값으로 채워짐:
```json
{
  "analysis_id": 2,
  "consultation_id": 6,
  "summary": "사건 유형: 임금체불 (임금을 3개월간 지급받지 못한 사례로 보임) / 긴급도: 중 / 법률구조 대상: 판단보류",
  "case_type": "임금체불",
  "case_subtype": null,
  "urgency_level": "중",
  "eligibility": "판단보류",
  "extracted_json": { "case_list": [{ "case_ratio": 0.9, "case_type": "임금체불", "case_type_reason": "..." }], "case_emergency_ratio": 0.5, "case_emergency_level": "중", "case_emergency_reason": "..." },
  "missing_info_json": [{ "item": "임금 지급 내역", "type": "증빙", "reason": "...", "confidence": 1.0, "reference_documents": [...] }],
  "checklist_json": { "eligibility": { "eligible": "판단보류", "evidence_status": "확인불가", ... }, "winnability": {...}, "executability": {...}, "appropriateness": {...}, "checklist_summary_for_lawyer": "..." },
  "recommendation_json": null,
  "timeline_json": null,
  "cluster_result_json": null,
  "estimated_time": null,
  "raw_input_json": { "content": { "summary": "...", "details": "...", "summited_file_link": [...], "consult_day": "2026-07-27" } },
  "created_at": "2026-07-27T17:46:58.057"
}
```
- `extracted_json`/`checklist_json`/`missing_info_json`은 ai-api 응답의 `case_analysis`/`relief_review_checklist`/`missing_items`를 그대로 저장한 것 — 필드 매핑은 [`ai-definition.md`](ai-definition.md) 참고
- `recommendation_json`/`timeline_json`/`cluster_result_json`/`case_subtype`/`estimated_time`은 이 파이프라인이 채우지 않아 항상 `null` (구 계약서 v0.1의 필드로, 아래 원시 CRUD 쪽에서만 쓰임)
- `raw_input_json`: ai-api에 실제로 보낸 요청 원문 (추적/디버깅용)
- ai-api 호출이 실패하면(연결 불가, 5xx 등) `502 Bad Gateway`로 응답

### POST /api/consultations/{consultationId}/analyses
분석 결과를 직접 만들어서(또는 `/analyze` 응답을 수정해서) 저장하는 원시 CRUD 엔드포인트. ai-api를 호출하지 않음.

Request
```json
{
  "summary": "2025년 4월부터 3개월분 임금 약 600만원을 지급받지 못한 임금체불 사건",
  "case_type": "임금체불",
  "case_subtype": "정기임금 미지급",
  "urgency_level": "중",
  "eligibility": "대상후보",
  "extracted_json": { "당사자": [...], "금액": 6000000, "날짜": {...}, "사건개요": "..." },
  "missing_info_json": ["근로계약서", "급여명세서", "통장 입금내역"],
  "checklist_json": [{ "항목": "관할 확인", "결과": "충족" }],
  "recommendation_json": { "법령": [...], "판례": [...], "유사사례": [] },
  "timeline_json": [{ "날짜": "2025-01", "내용": "입사" }],
  "cluster_result_json": [],
  "estimated_time": null,
  "raw_input_json": null
}
```
- `consultation_id`는 body에 넣지 않음 — URL 경로에서 받음 (Attachment 업로드와 같은 방식)
- `_json`으로 끝나는 필드는 구조가 자유로운 JSON (객체/배열 무엇이든 가능) — DB엔 Postgres `jsonb`로 저장됨

Response `201` — 계약서와 동일한 형태 + `analysis_id`, `consultation_id`, `created_at` 포함

### GET /api/consultations/{consultationId}/analyses
해당 상담의 분석 결과 전체 (재분석 이력 포함, `/analyze`로 생성된 것과 `/analyses`로 직접 저장된 것 모두 포함). 상담이 없으면 `404`.

### GET /api/consultations/{consultationId}/analyses/{analysisId}
단건 조회. 없으면 `404`.

### PUT /api/consultations/{consultationId}/analyses/{analysisId}
부분 수정 — body에 넣은 필드만 갱신 (Consultation의 PUT과 같은 방식). `raw_input_json`도 같은 방식으로 갱신 가능.

### DELETE /api/consultations/{consultationId}/analyses/{analysisId}
분석 결과 삭제. Response `204`

상담(Consultation) 삭제 시 딸린 AI_ANALYSIS도 함께 삭제됨 (cascade).

---

## 파일 저장 방식

**S3** (`app.s3.bucket`, 기본값 `aivle-test-ai-34178924` / 리전 `ap-northeast-2`). key는
`consult-attachments/{uuid}__{원본파일명}` (presigned 업로드) 또는 `{consultationId}/{uuid}__{원본파일명}`
(서버 경유 업로드) 형태. ai-api의 `/consult/analyze`가 이 S3 버킷에서 파일을 직접 읽으므로,
core-api(`app.s3.bucket`)와 ai-api(`.env`의 `S3_BUCKET_NAME`)가 항상 같은 버킷을 가리켜야 함.
로컬 디스크 저장(`FileStorageService`, `./uploads`)은 코드상 남아있지만 현재 `AttachmentService`/
`ConsultationService`는 사용하지 않음 (S3로 전환됨).

---

## 아직 없는 것

- `case_type`/`urgency_level`/`eligibility`/`checklist_json` 값 확정 (팀 회의 대기 중)
- 인증/로그인 (`SESSION`, `OAUTH`), `User` 수정/삭제, 비밀번호 처리
- `GENERATED_DOCUMENT`, `LEGAL_TEMPLATE`, `CONSULTATION_LOG`
- 자동화 테스트, 헬스체크 엔드포인트
- STT/OCR 결과를 `Attachment.extractedText`로 되채우는 파이프라인 (현재는 `AI_ANALYSIS.extracted_json` 쪽에만 반영)
- ai-api의 구 `/analysis`(Gemini, 계약서 전용) 및 레거시 3분리 엔드포인트(`/case-analysis`, `/eligibility/analyze`, `/missing-data/analyze`)는 core-api와 연동되지 않음 — `/consult/analyze` 통합 파이프라인만 사용
