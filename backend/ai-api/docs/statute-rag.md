# 현행법령 RAG 운영 문서

## 1. 개요

현행법령 RAG는 국가법령정보 공동활용 API에서 법령 원문을 수집한 뒤
조문 단위로 분리하고, 로컬 임베딩 모델과 Chroma를 사용해 관련 조문을
검색하는 기능이다.

상담 요청마다 국가법령정보 API를 호출하지 않는다.

동작 흐름은 다음과 같다.

```text
국가법령정보 API
→ 현행 법령 수집
→ 조문 파싱
→ 조문 청크 생성
→ multilingual-e5-small 임베딩
→ Chroma legal_statutes 컬렉션 저장
→ 상담 분석 결과로 관련 조문 검색
→ /consult/analyze 응답의 related_statutes에 포함
```

법령 검색이나 로컬 인덱스에 장애가 발생해도 상담 분석 전체는 중단하지
않고 `related_statutes: []`로 계속 진행한다.

## 2. 현재 구축 대상 법령

초기 구축 대상은 다음 5개 법령이다.

1. 민법
2. 가사소송법
3. 가족관계의 등록 등에 관한 법률
4. 민사소송법
5. 민사집행법

최초 구축 시점의 참고 수치는 다음과 같다.

```text
법령 수: 5
원본 조문 수: 2,258
생성 청크 수: 2,289
Chroma 저장 수: 2,289
```

법령 개정에 따라 조문 및 청크 수는 달라질 수 있다.

## 3. 주요 구성

```text
rag/statute_api.py
    국가법령정보 현행법령 목록·본문 API 호출

rag/statute_parser.py
    API 응답에서 실제 조문만 추출

rag/statute_documents.py
    조문을 RAG 문서와 청크로 변환

rag/build_statute_index.py
    대상 법령 수집·임베딩·Chroma 저장

rag/statute_retriever.py
    벡터 검색, 조문 중복 제거, 경량 재정렬

rag/evaluate_statute_retrieval.py
    대표 질의 검색 정확도 평가

app/ai/statutes/rag_results.py
    내부 검색 결과를 애플리케이션 응답 형식으로 변환

app/ai/statutes/service.py
    구조화된 상담 분석 결과로 검색 질의 생성

app/routers/consult.py
    /consult/analyze 응답에 related_statutes 연결
```

## 4. 모델과 저장소

```text
임베딩 모델: intfloat/multilingual-e5-small
벡터 차원: 384
문서 접두어: passage:
질의 접두어: query:
정규화: 사용
벡터 저장소: Chroma
컬렉션: legal_statutes
저장 경로: backend/ai-api/storage/chroma
```

`storage/chroma`는 Git에 포함하지 않는다. 각 실행 환경에서 인덱스를
직접 생성해야 한다.

## 5. 환경변수

`backend/ai-api/.env`에 국가법령정보 공동활용 API의 OC 값을 설정한다.

```text
LAW_API_OC=<발급받은 OC 값>
```

애플리케이션 전체 실행에는 기존 설정도 필요하다.

```text
OPENAI_API_KEY=<OpenAI API 키>
S3_BUCKET_NAME=<S3 버킷 이름>
```

`HF_TOKEN`은 필수가 아니다. 설정하지 않으면 Hugging Face Hub의
비인증 요청 경고가 나올 수 있지만, 이미 모델을 내려받은 환경에서는
검색 기능이 정상적으로 동작한다.

실제 환경변수 값과 `.env` 파일은 Git에 커밋하지 않는다.

## 6. 인덱스 생성

`backend/ai-api`에서 실행한다.

```powershell
.\venv\Scripts\python.exe -m rag.build_statute_index
```

완료 시 다음 항목을 확인한다.

```text
=== Statute indexing complete ===
Statutes: 5
Source articles: ...
Generated chunks: ...
Stored records: ...
Collection: legal_statutes
```

법령 API 수집 과정에서 오류가 발생하면 임베딩과 저장을 시작하지 않으므로
일부 법령만 반영된 불완전한 인덱스가 생성되지 않는다.

## 7. 검색 품질 평가

```powershell
.\venv\Scripts\python.exe -m rag.evaluate_statute_retrieval
```

현재 대표 평가 항목은 다음과 같다.

```text
재산분할청구권
면접교섭권
상속의 순위
배우자의 상속순위
가사소송상 재산조회
```

기준 결과:

```text
Cases: 5
Top-1 hits: 5
Top-3 hits: 5
```

## 8. 테스트

법령 관련 테스트:

```powershell
.\venv\Scripts\python.exe -m pytest `
  .\tests\test_statute_api.py `
  .\tests\test_statute_parser.py `
  .\tests\test_statute_documents.py `
  .\tests\test_statute_vector_store.py `
  .\tests\test_build_statute_index.py `
  .\tests\test_statute_retriever.py `
  .\tests\test_statute_rag_results.py `
  .\tests\test_statute_service.py `
  .\tests\test_statute_consult_integration.py `
  .\tests\test_statute_resilience.py `
  -q
```

프로젝트 전체 테스트:

```powershell
.\venv\Scripts\python.exe -m pytest .\tests -q
```

의존성 검사:

```powershell
.\venv\Scripts\python.exe -m pip check
```

## 9. API 응답

`POST /consult/analyze` 응답에 다음 필드가 추가된다.

```json
{
  "related_statutes": [
    {
      "law_id": "001706",
      "law_name": "민법",
      "article_label": "제839조의2",
      "article_title": "재산분할청구권",
      "citation": "민법 제839조의2(재산분할청구권)",
      "effective_date": "20260317",
      "content": "조문 내용",
      "similarity": 0.9015,
      "rerank_score": 0.9815
    }
  ]
}
```

검색 실패, 인덱스 미생성 또는 실질적인 상담 내용이 없는 경우에는 다음과
같이 반환한다.

```json
{
  "related_statutes": []
}
```

## 10. 법령 갱신 절차

법령 개정 내용을 반영할 때 다음 순서로 실행한다.

```text
1. LAW_API_OC 설정 확인
2. python -m rag.build_statute_index
3. python -m rag.evaluate_statute_retrieval
4. 법령 관련 테스트 실행
5. 프로젝트 전체 테스트 실행
```

법령 데이터와 Chroma 저장 파일은 커밋하지 않는다. 코드 변경이 없다면
인덱스 재생성만 수행한다.

## 11. 문제 해결

### LAW_API_OC 오류

`.env`의 `LAW_API_OC`가 비어 있거나 올바르지 않은지 확인한다. 실제 값을
터미널 출력이나 Git diff에 노출하지 않는다.

### Hugging Face 비인증 경고

다음 경고는 오류가 아니다.

```text
Warning: You are sending unauthenticated requests to the HF Hub.
```

다운로드 제한이 문제가 되는 배포 환경에서만 `HF_TOKEN`을 설정한다.

### 빈 인덱스

`legal_statutes` 컬렉션이 비어 있으면 검색 결과는 빈 목록으로 반환된다.
다음 명령으로 인덱스를 구축한다.

```powershell
.\venv\Scripts\python.exe -m rag.build_statute_index
```

### Windows 임시 폴더 삭제 오류

Chroma가 `chroma.sqlite3`를 사용 중인 상태에서 Python의
`TemporaryDirectory`가 즉시 폴더를 지우면 `WinError 32`가 발생할 수 있다.
Python 프로세스 종료 후 PowerShell에서 임시 폴더를 삭제하면 된다.