from pathlib import Path


# backend/ai-api/rag/config.py
RAG_DIR = Path(__file__).resolve().parent
AI_API_DIR = RAG_DIR.parent

DATA_DIR = RAG_DIR / "data"
STORAGE_DIR = AI_API_DIR / "storage"
CHROMA_DB_DIR = STORAGE_DIR / "chroma"

# 임베딩 모델
EMBEDDING_MODEL_NAME = "intfloat/multilingual-e5-small"

# ChromaDB 컬렉션
COLLECTION_NAME = "legal_documents"
LEGAL_FORMS_COLLECTION_NAME = "legal_forms"
LEGAL_STATUTES_COLLECTION_NAME = "legal_statutes"
LEGAL_PRECEDENTS_COLLECTION_NAME = "legal_precedents"

# 데이터 파일
CLASSIFICATION_PATH = DATA_DIR / "case_classification.json"
DOCUMENTS_PATH = DATA_DIR / "documents.json"
MOCK_DOCUMENTS_PATH = DATA_DIR / "documents.mock.json"
EVALUATION_QUERIES_PATH = DATA_DIR / "evaluation_queries.json"
TEMPLATE_MANIFEST_PATH = DATA_DIR / "template_manifest.json"
PARSED_TEMPLATES_PATH = DATA_DIR / "parsed_templates.json"
PARSED_FORMS_PATH = AI_API_DIR / "parsed" / "전체.json"

# 검색 설정
DEFAULT_TOP_K = 3

# 사건 분류 신뢰도 기준
HIGH_CONFIDENCE = 0.75
MEDIUM_CONFIDENCE = 0.50
