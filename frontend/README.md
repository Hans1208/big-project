# 대한법률구조공단 상담 지원 포털 — Frontend

법률구조 상담 업무(상담 접수 → AI 분석 → 변호사 검토 → 서식 생성)를 **상담원 · 변호사 · 관리자**
세 역할별 화면으로 제공하는 웹 프론트엔드입니다.

```bash
npm install
npm run dev      # 개발 서버 (기본 http://localhost:5173)
npm run build    # 프로덕션 빌드
npm run lint     # oxlint 정적 검사
```

> 로그인 화면의 **테스트용 빠른 로그인**으로 계정 없이 세 역할을 바로 확인할 수 있습니다.
> 기술 스택: React 19 + Vite, lucide-react 아이콘, 순수 CSS 디자인 토큰(`styles/global.css`).

---

## 폴더 구조

```
src/
├── App.jsx                최상위. 로그인/대시보드 전환, 전역 상태(상담·검토·알림·사용자) 관리
├── main.jsx               엔트리
├── constants.jsx          공통 상수(역할 옵션, 오늘 날짜 등)
├── components/
│   ├── layout.jsx         헤더(로고·역할별 메뉴·알림 배지)·푸터
│   ├── common.jsx         요약 카드·상담 표·달력·확인 모달 등 공용 UI
│   ├── loading.jsx        전역 로딩 오버레이 Provider
│   └── feedback.jsx       앱 내부 토스트·확인창 Provider
├── pages/
│   ├── auth.jsx           로그인 / 회원가입 / 비밀번호 찾기
│   ├── dashboards.jsx     상담원·변호사·관리자 대시보드 + 차트
│   └── workflows.jsx      상담 등록·분석·법률판례 검색·서식 생성·알림·프로필 화면
├── services/
│   ├── storage.js         localStorage 저장 + 감사 로그
│   ├── legalAidApi.js     목업 API·payload 변환 유틸
│   ├── aiApiClient.js     ai-api(FastAPI) 호출 클라이언트
│   ├── coreApiClient.js   core-api(Spring) 호출 클라이언트
│   └── s3UploadClient.js  브라우저 → S3 직접 업로드
├── data/
│   ├── domain.js          사건 분류(가사법 4대), 지부·첨부 유형 등
│   └── legalTemplateSeed.js  법률 서식 시드(약 291종)
├── utils/
│   ├── date.js            달력·날짜 유틸
│   └── statusTone.js      상태 단어 → 색 톤 매핑(색상 일관성 단일 기준)
└── styles/global.css      전역 디자인 토큰 및 전체 스타일
```

---

## 백엔드 연동 현황

프론트는 **두 백엔드**와 통신합니다(Vite 프록시: `/ai-api` → :8001, `/core-api` → :8080).
핵심은 **백엔드가 꺼져 있어도 로컬 목업/저장으로 폴백**해 전 화면이 동작한다는 점입니다.

| 대상 | 파일 | 상태 |
|---|---|---|
| 로컬 저장(상담·검토·사용자·알림·감사로그) | `storage.js` | ✅ 완료 (localStorage 기반 기본 저장소) |
| AI 분석 `/analysis` (계약 mock) | `aiApiClient.js` | ✅ 호출 연동, 실패 시 로컬 목업 폴백 |
| AI 분석 `/case-analysis`·`/eligibility`·`/missing-data` | `aiApiClient.js` | ⚠️ 호출부는 준비됨, **실제 OpenAI 키 필요** |
| 상담·사용자·분석 저장(Core) | `coreApiClient.js` | ⚠️ 호출부 준비됨, 서버 켜지면 자동 사용(실패해도 로컬 저장 유지) |
| 파일 업로드(S3 presigned) | `s3UploadClient.js` | ⚠️ 프론트 준비됨, **백엔드 presigned 엔드포인트 대기** (없으면 로컬 임시 보관) |
| 서식 파일(HWPX) 생성 | `workflows.jsx` | ⛔ 미연동 (초안 미리보기까지만, document-api 대기) |
| 법령·판례 추천 | `legalAidApi.js` | ⛔ 목업 후보 목록 (추천 API 대기) |

- 관리자 → **운영 관리**에서 각 백엔드 연결 상태를 눌러 확인할 수 있습니다.
- 베이스 URL은 환경변수(`VITE_AI_API_BASE_URL`, `VITE_CORE_API_BASE_URL`)로 덮어쓸 수 있습니다.
- S3 presigned 엔드포인트 규격은 `s3UploadClient.js` 상단 주석 참고.

---

## 역할별 기능

### 공통
- 회원가입 / 로그인 / 비밀번호 찾기 (상담원·변호사는 관리자 승인 후 로그인 가능, 관리자는 즉시)
- 테스트용 빠른 로그인 · 알림(읽음/삭제) · 프로필 수정 · 감사 로그 기록

### 상담원 (Counselor)
- 요약 카드(총/진행 중/완료/보류, 클릭 필터) · 최근 상담 목록(검색·삭제) · 일정별 상담 목록(달력)
- 보완 요청 상담(변호사가 되돌린 건 모아보기)
- **상담 등록** — 첨부(녹취·신분증·증빙) 업로드, 법률구조 대상 자격 체크
- **상담 분석** — AI 요약·사건유형·긴급도·구조대상 후보, 누락자료·체크리스트, STT 마스킹, 타임라인, 변호사 검토 요청
- **법률·판례 검색 / 서식 생성**

### 변호사 (Lawyer)
- 요약 카드(검토 대기/검토 중/승인/반려) · 검토 요청 목록 · 검토 결정 로그
- **HITL 검토 결정 모달** — AI 결과는 참고용, 사람이 확인 후 결정(승인/수정 요청/추가자료 요청/반려/보류) + 사유 확정

### 관리자 (Admin)
- 요약 카드(전체 상담·활성 사용자·분석 처리율·승인 대기)
- 전체 상담 현황(주별 그래프) · 사건 유형별 통계 · 분석 처리 현황(도넛)
- 활성 사용자 현황 · 회원가입 승인/거절
- **운영 관리** — 감사 로그, 서식 개정 모니터링, 백엔드 연결 상태 확인
