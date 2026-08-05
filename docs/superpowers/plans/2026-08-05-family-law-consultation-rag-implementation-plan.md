# Family-Law Consultation RAG Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Normalize four Korea Legal Aid Corporation consultation CSV files, build a `legal_consultations` Chroma collection for family-law retrieval, and connect Top-3 similar consultations to the consultation analysis flow using only `anonymized_text`.

**Architecture:** Raw CP949 CSV files remain under ignored local storage. Focused loader, normalizer, document/chunk builder, index builder, retriever, evaluator, and API service modules are implemented independently with TDD. Statutes and precedents remain the authoritative sources; similar consultations are returned only as lower-priority reference material.

**Tech Stack:** Python 3.12, pytest, csv, html, hashlib, json, ChromaDB, `intfloat/multilingual-e5-small`, FastAPI/Pydantic, Java/Spring Boot DTO integration, PowerShell on Windows.

## Global Constraints

- Work only on branch `feat/consultation-rag`.
- Raw files, processed JSONL, reports, and Chroma data stay under `backend/ai-api/storage/` and are never committed.
- Read source CSV files with `cp949`.
- Expected source data rows: basic part 1 = 1,484; basic part 2 = 3,966; case part 1 = 1,938; case part 2 = 3,438.
- Expected family-law candidate rows before normalization/deduplication: 360 + 513 + 792 + 0 = 1,665.
- Family-law service categories are exactly `family_litigation`, `family_registration`, `inheritance`, and `kinship`.
- Collection name is exactly `legal_consultations`.
- Embedding model is `intfloat/multilingual-e5-small`, dimension 384, normalized embeddings, `passage:` document prefix, and `query:` query prefix.
- Chunk size is 800 characters with 120-character overlap.
- Search returns at most three unique consultations, targeting at most two `case` results and at most one `basic` result before fallback filling.
- Each API result exposes at most 1,000 characters in `answer_excerpt`.
- Retrieval input is only `anonymized_text`; no fallback to raw `summary`, `details`, transcripts, or attachments.
- Missing index, blank anonymized input, or retrieval error returns `[]` and must not fail the overall analysis.
- Similar consultations are reference material and must be presented after statutes and precedents.
- Use `.\venv\Scripts\python.exe` for every Python command.
- Follow RED → GREEN, run focused tests, and commit explicit files only. Never use `git add .`.

---

## File Responsibility Map

### New runtime modules

- `backend/ai-api/rag/consultation_loader.py`
  - Declares the four expected source specifications.
  - Reads CP949 CSV files.
  - Validates headers and source row counts.
  - Produces raw row records with source metadata.

- `backend/ai-api/rag/consultation_normalizer.py`
  - Cleans HTML and whitespace.
  - Filters family-law rows.
  - Maps rows to the four service categories.
  - Detects missing values, duplicates, and personal-information candidates.
  - Creates stable `consultation_id` values.
  - Writes UTF-8 JSONL and a normalization report.

- `backend/ai-api/rag/consultation_documents.py`
  - Converts normalized consultations into 800/120 answer chunks.
  - Repeats category and question in every chunk.
  - Produces Chroma IDs, documents, and metadata.

- `backend/ai-api/rag/build_consultation_index.py`
  - Runs loading, normalization, chunking, embedding, and upsert.
  - Creates only the `legal_consultations` collection.
  - Validates generated and stored counts.

- `backend/ai-api/rag/consultation_retriever.py`
  - Retrieves candidate chunks.
  - Applies category/lexical/source-type reranking.
  - Deduplicates by `consultation_id`.
  - Returns balanced Top-3 results.

- `backend/ai-api/rag/evaluate_consultation_retrieval.py`
  - Runs 12 paraphrased family-law queries.
  - Reports category hits, expected-term hits, duplicates, failures, and obvious noise.
  - Enforces the agreed quality gate.

### New service modules

- `backend/ai-api/app/ai/consultations/__init__.py`
- `backend/ai-api/app/ai/consultations/rag_results.py`
  - Converts retriever dictionaries into stable API result dictionaries.
  - Truncates `answer_excerpt` to 1,000 characters.

- `backend/ai-api/app/ai/consultations/service.py`
  - Fail-open wrapper around consultation retrieval.
  - Rejects blank anonymized text.

### Modified modules

- `backend/ai-api/rag/config.py`
  - Adds `LEGAL_CONSULTATIONS_COLLECTION_NAME = "legal_consultations"`.

- `backend/ai-api/app/ai/consult/rag_service.py`
  - Collects consultation results alongside statutes and precedents.
  - Passes only the supplied anonymized content.

- `backend/ai-api/app/ai/consult/schemas.py`
  - Adds `related_consultations` to the Python analysis response.

- `backend/ai-api/app/routers/consult.py`
  - Adds lower-priority similar-consultation context after statutes and precedents.

- `backend/core-api/src/main/java/com/aivle/bigproject/analysis/client/...`
  - Adds the matching Java response DTO field if the current response model requires it.

### New tests

- `backend/ai-api/tests/test_consultation_loader.py`
- `backend/ai-api/tests/test_consultation_normalizer.py`
- `backend/ai-api/tests/test_consultation_documents.py`
- `backend/ai-api/tests/test_build_consultation_index.py`
- `backend/ai-api/tests/test_consultation_retriever.py`
- `backend/ai-api/tests/test_evaluate_consultation_retrieval.py`
- `backend/ai-api/tests/test_consultation_rag_results.py`
- `backend/ai-api/tests/test_consultation_service.py`
- Update existing consultation integration and anonymized-input contract tests.

---

### Task 1: Place and audit the four raw CSV files

**Files:**
- Runtime only: `backend/ai-api/storage/legal_consultations/raw/basic_qa_part1_20240731.csv`
- Runtime only: `backend/ai-api/storage/legal_consultations/raw/basic_qa_part2_20240731.csv`
- Runtime only: `backend/ai-api/storage/legal_consultations/raw/case_qa_part1_20240731.csv`
- Runtime only: `backend/ai-api/storage/legal_consultations/raw/case_qa_part2_20240731.csv`
- Runtime only: `backend/ai-api/storage/legal_consultations/reports/raw_audit.json`

**Interfaces:**
- Consumes: four original CSV files selected by the developer.
- Produces: canonical filenames and an audit report containing SHA-256, headers, total rows, and family-law rows.

- [ ] **Step 1: Copy selected CSV files into canonical runtime paths**

Use a local selection script that identifies each file by headers and exact row count rather than depending on Korean filenames.

- [ ] **Step 2: Verify CP949 decoding and source structure**

Expected headers:

```python
{
    "basic_part1": ("법률분류", "기본질문", "기본답변"),
    "basic_part2": ("법률분류", "기본질문", "기본답변"),
    "case_part1": ("법률분류", "유사질문", "유사답변"),
    "case_part2": ("법률분류", "유사질문", "유사답변", "주요법령", "판례"),
}
```

Expected data rows:

```python
{
    "basic_part1": 1484,
    "basic_part2": 3966,
    "case_part1": 1938,
    "case_part2": 3438,
}
```

Expected family-law rows:

```python
{
    "basic_part1": 360,
    "basic_part2": 513,
    "case_part1": 792,
    "case_part2": 0,
}
```

- [ ] **Step 3: Verify storage remains ignored**

Run:

```powershell
git check-ignore -v .\storage\legal_consultations\raw\basic_qa_part1_20240731.csv
git status --short
```

Expected: the file is matched by `.gitignore`, and Git status remains clean.

---

### Task 2: Implement the CP949 loader

**Files:**
- Create: `backend/ai-api/rag/consultation_loader.py`
- Create: `backend/ai-api/tests/test_consultation_loader.py`

**Interfaces:**
- Produces: `ConsultationSourceSpec`, `RawConsultationRow`, `default_source_specs(raw_dir)`, `load_consultation_source(spec)`, and `load_all_consultation_sources(raw_dir)`.

- [ ] **Step 1: Write failing tests**

Tests must cover:
- all four default source specifications;
- CP949 decoding;
- exact headers;
- exact row counts;
- source type and source row metadata;
- missing file error;
- unexpected header error;
- invalid CP949 error.

- [ ] **Step 2: Run the focused test and confirm RED**

```powershell
.\venv\Scripts\python.exe -m pytest .\tests\test_consultation_loader.py -q
```

Expected: import failure because `rag.consultation_loader` does not exist.

- [ ] **Step 3: Implement the minimal loader**

Use `csv.DictReader`, `encoding="cp949"`, and `newline=""`. Error messages must include the canonical source filename but not row contents.

- [ ] **Step 4: Run GREEN**

```powershell
.\venv\Scripts\python.exe -m pytest .\tests\test_consultation_loader.py -q
```

- [ ] **Step 5: Commit**

```powershell
git add .\rag\consultation_loader.py .\tests\test_consultation_loader.py
git commit -m "feat: load consultation CSV sources"
```

---

### Task 3: Normalize, classify, deduplicate, and report

**Files:**
- Create: `backend/ai-api/rag/consultation_normalizer.py`
- Create: `backend/ai-api/tests/test_consultation_normalizer.py`
- Runtime only: `backend/ai-api/storage/legal_consultations/processed/family_consultations.jsonl`
- Runtime only: `backend/ai-api/storage/legal_consultations/reports/normalization_report.json`

**Interfaces:**
- Consumes: `Sequence[RawConsultationRow]`.
- Produces: `NormalizedConsultation`, `normalize_text`, `map_service_category`, `find_personal_information_candidates`, `normalize_consultations`, and `write_normalized_outputs`.

- [ ] **Step 1: Write failing normalization tests**

Tests must prove:
- HTML tags are removed;
- HTML entities are decoded;
- repeated whitespace is normalized;
- blank question/answer rows are excluded;
- only `가족관계등록>`, `상속과유언>`, and `친족>` are candidates;
- family litigation topics under `친족>` map to `family_litigation`;
- remaining covered kinship topics map to `kinship`;
- exact duplicates collapse;
- stable IDs do not change between runs;
- phone, resident-registration, and email candidates fail the build and are counted in the report.

- [ ] **Step 2: Confirm RED**

```powershell
.\venv\Scripts\python.exe -m pytest .\tests\test_consultation_normalizer.py -q
```

- [ ] **Step 3: Implement minimal normalization**

Stable ID input:

```python
stable_key = "\n".join(
    (
        source_type,
        normalize_text(question),
        normalize_text(answer),
    )
)
consultation_id = "consultation-" + hashlib.sha256(
    stable_key.encode("utf-8")
).hexdigest()[:24]
```

Deduplicate by normalized `(question, answer)` while preserving the first source occurrence.

- [ ] **Step 4: Generate and validate real outputs**

The pre-deduplication family-law candidate count must be exactly 1,665. The post-deduplication count must be reported explicitly and is expected to be 1,664 or 1,665. Personal-information candidates must be zero before indexing.

- [ ] **Step 5: Run GREEN and commit**

```powershell
.\venv\Scripts\python.exe -m pytest .\tests\test_consultation_normalizer.py -q
git add .\rag\consultation_normalizer.py .\tests\test_consultation_normalizer.py
git commit -m "feat: normalize family-law consultations"
```

---

### Task 4: Build consultation documents and chunks

**Files:**
- Create: `backend/ai-api/rag/consultation_documents.py`
- Create: `backend/ai-api/tests/test_consultation_documents.py`

**Interfaces:**
- Consumes: `NormalizedConsultation`.
- Produces: `ConsultationChunk`, `build_consultation_chunks(consultations, chunk_size=800, overlap=120)`, and `chunks_to_vector_records`.

- [ ] **Step 1: Write failing chunk tests**

Tests must verify:
- every document starts with `passage:`;
- legal path and full question appear in every chunk;
- only the answer body is windowed;
- chunk size is 800 and overlap is 120;
- no empty chunks;
- unique vector IDs;
- metadata includes consultation ID, source type, service category, legal path, source date, question, answer, and chunk index.

- [ ] **Step 2: Confirm RED**

```powershell
.\venv\Scripts\python.exe -m pytest .\tests\test_consultation_documents.py -q
```

- [ ] **Step 3: Implement and run GREEN**

```powershell
.\venv\Scripts\python.exe -m pytest .\tests\test_consultation_documents.py -q
```

- [ ] **Step 4: Commit**

```powershell
git add .\rag\consultation_documents.py .\tests\test_consultation_documents.py
git commit -m "feat: chunk consultation documents"
```

---

### Task 5: Build the Chroma consultation index

**Files:**
- Modify: `backend/ai-api/rag/config.py`
- Create: `backend/ai-api/rag/build_consultation_index.py`
- Create: `backend/ai-api/tests/test_build_consultation_index.py`

**Interfaces:**
- Adds: `LEGAL_CONSULTATIONS_COLLECTION_NAME = "legal_consultations"`.
- Produces: `build_consultation_index(raw_dir, processed_dir, reports_dir, store=None) -> dict[str, int]`.

- [ ] **Step 1: Write failing index tests**

Tests must verify:
- exact collection name;
- loader → normalizer → chunk builder flow;
- stored count equals chunk count;
- empty normalized data fails;
- personal-information candidates fail before embeddings;
- statutes, forms, and precedents collections are not deleted or rewritten.

- [ ] **Step 2: Confirm RED**

```powershell
.\venv\Scripts\python.exe -m pytest .\tests\test_build_consultation_index.py -q
```

- [ ] **Step 3: Implement the index builder**

Reuse the existing embedding and vector-store abstractions. Do not create a second embedding model configuration.

- [ ] **Step 4: Run focused and related tests**

```powershell
.\venv\Scripts\python.exe -m pytest .\tests\test_build_consultation_index.py .\tests\test_precedent_vector_store.py -q
```

- [ ] **Step 5: Build the real collection and validate counts**

Back up `storage/chroma`, delete only `legal_consultations` if it exists, build, and restore the backup on any failed validation.

- [ ] **Step 6: Commit**

```powershell
git add .\rag\config.py .\rag\build_consultation_index.py .\tests\test_build_consultation_index.py
git commit -m "feat: build consultation vector index"
```

---

### Task 6: Implement retrieval, balancing, and quality evaluation

**Files:**
- Create: `backend/ai-api/rag/consultation_retriever.py`
- Create: `backend/ai-api/rag/evaluate_consultation_retrieval.py`
- Create: `backend/ai-api/tests/test_consultation_retriever.py`
- Create: `backend/ai-api/tests/test_evaluate_consultation_retrieval.py`

**Interfaces:**
- Produces: `ConsultationRetriever.search(query, top_k=3, candidate_k=24)`.
- Produces: `retrieve_consultations(query, top_k=3)`.
- Produces: `evaluate_consultation_retrieval` and `quality_gate_failures`.

- [ ] **Step 1: Write failing retriever tests**

Tests must prove:
- query documents use `query:`;
- blank query returns `[]`;
- candidate count is at least 15;
- repeated chunks collapse by consultation ID;
- results contain at most two case records and one basic record before fallback;
- unavailable collection and query errors return `[]`;
- output is capped at Top-3.

- [ ] **Step 2: Implement and pass retriever tests**

```powershell
.\venv\Scripts\python.exe -m pytest .\tests\test_consultation_retriever.py -q
```

- [ ] **Step 3: Add 12 evaluation cases**

Use three paraphrased user queries per category:
- divorce/property division, child support, visitation;
- family-register correction, missing birth registration, name/surname registration;
- reserved share/will, inheritance renunciation, inheritance division;
- adoption/dissolution, parent-child relationship, adult/minor guardianship.

- [ ] **Step 4: Implement evaluation gates**

Required gates:
- category Top-3 = 12/12;
- expected-term Top-3 >= 10/12;
- duplicate consultations = 0;
- retrieval failures = 0;
- obvious non-family-law noise = 0.

- [ ] **Step 5: Run real evaluation and inspect Top-3**

Do not tune solely for Top-1. Stop only when the defined Top-3 gates pass.

- [ ] **Step 6: Commit**

```powershell
git add .\rag\consultation_retriever.py .\rag\evaluate_consultation_retrieval.py .\tests\test_consultation_retriever.py .\tests\test_evaluate_consultation_retrieval.py
git commit -m "feat: retrieve similar consultations"
```

---

### Task 7: Connect consultation results to the analysis API

**Files:**
- Create: `backend/ai-api/app/ai/consultations/__init__.py`
- Create: `backend/ai-api/app/ai/consultations/rag_results.py`
- Create: `backend/ai-api/app/ai/consultations/service.py`
- Create: `backend/ai-api/tests/test_consultation_rag_results.py`
- Create: `backend/ai-api/tests/test_consultation_service.py`
- Modify: `backend/ai-api/app/ai/consult/rag_service.py`
- Modify: `backend/ai-api/app/ai/consult/schemas.py`
- Modify: `backend/ai-api/app/routers/consult.py`
- Modify existing anonymized-contract and integration tests.
- Modify matching Java response DTO/service files only after locating the current concrete types.

**Interfaces:**
- Produces: `collect_related_consultations(anonymized_text: str, top_n: int = 3) -> list[dict[str, object]]`.
- Extends consultation source aggregation with `related_consultations`.

- [ ] **Step 1: Write failing result-shaping and service tests**

Tests must cover exact response keys, answer excerpt limit, blank input, retrieval exception, and fail-open behavior.

- [ ] **Step 2: Implement result shaping and fail-open service**

Every result contains:
`consultation_id`, `source_type`, `service_category`, `legal_path`, `question`, `answer_excerpt`, `similarity`, and `source_date`.

- [ ] **Step 3: Write failing anonymized integration tests**

The fake consultation retriever must receive only `content.anonymized_text`. Tests must fail if raw summary, details, transcript text, or attachment text is passed or used as fallback.

- [ ] **Step 4: Connect source aggregation and prompt context**

Order context as statutes, precedents, then:

```text
[유사 상담사례 — 법적 근거가 아닌 참고자료]
```

- [ ] **Step 5: Update Python and Java contracts**

Locate the current `ConsultAnalyzeResponse` and Java AI analysis response DTO before editing. Add the field without renaming existing fields.

- [ ] **Step 6: Run focused integration tests**

```powershell
.\venv\Scripts\python.exe -m pytest .\tests\test_consultation_rag_results.py .\tests\test_consultation_service.py .\tests\test_consult_rag_service.py .\tests\test_core_anonymized_text_contract.py -q
```

- [ ] **Step 7: Commit**

Stage only the explicit Python and Java files changed for consultation integration.

```powershell
git commit -m "feat: connect anonymized consultation RAG"
```

---

### Task 8: Full verification and delivery

**Files:**
- No new runtime files.
- Remove local reports/logs/backups only after all checks pass.

- [ ] **Step 1: Run complete Python tests**

```powershell
.\venv\Scripts\python.exe -m pytest -q
```

- [ ] **Step 2: Validate dependencies**

```powershell
.\venv\Scripts\python.exe -m pip check
```

- [ ] **Step 3: Run core-api tests**

From `backend/core-api`:

```powershell
.\gradlew.bat test --rerun-tasks
```

- [ ] **Step 4: Rebuild and validate the real consultation collection**

Required:
- candidate rows = 1,665;
- normalized rows = 1,664 or 1,665;
- personal-information candidates = 0;
- failed records = 0;
- stored vectors = generated chunks;
- other Chroma collections remain present.

- [ ] **Step 5: Run the 12-query quality gate**

Required:
- category Top-3 = 12/12;
- expected-term Top-3 >= 10/12;
- duplicates = 0;
- failures = 0;
- obvious noise = 0.

- [ ] **Step 6: Verify Git state**

```powershell
git diff --check
git status --short
git rev-list --left-right --count origin/master...HEAD
```

- [ ] **Step 7: Push branch**

```powershell
git push origin feat/consultation-rag
```

- [ ] **Step 8: Prepare PR summary**

Report actual normalized record count, chunk count, stored count, category counts, quality scores, Python test count, dependency check, and Gradle result. Do not commit raw or generated storage files.
