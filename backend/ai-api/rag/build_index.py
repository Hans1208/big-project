import json
from pathlib import Path

import chromadb
from sentence_transformers import SentenceTransformer

from classification import (
    load_case_classification,
    validate_case_classification,
)


BASE_DIR = Path(__file__).resolve().parent
DATA_PATH = BASE_DIR / "data" / "documents.json"
DB_PATH = BASE_DIR.parent / "storage" / "chroma"

MODEL_NAME = "intfloat/multilingual-e5-small"
COLLECTION_NAME = "legal_documents"

REQUIRED_FIELDS = {
    "id",
    "document_type",
    "case_type",
    "case_subtype",
    "title",
    "content",
}


def load_documents() -> list[dict]:
    """문서 JSON을 읽고 필수 필드와 사건 분류를 검증한다."""
    if not DATA_PATH.exists():
        raise FileNotFoundError(
            f"데이터 파일을 찾을 수 없습니다: {DATA_PATH}"
        )

    with DATA_PATH.open("r", encoding="utf-8") as file:
        documents = json.load(file)

    if not isinstance(documents, list) or not documents:
        raise ValueError("저장할 문서가 없습니다.")

    classification = load_case_classification()

    for index, document in enumerate(documents, start=1):
        missing_fields = REQUIRED_FIELDS - document.keys()

        if missing_fields:
            raise ValueError(
                f"{index}번째 문서에 필수 필드가 없습니다: "
                f"{', '.join(sorted(missing_fields))}"
            )

        validate_case_classification(
            case_type=document["case_type"],
            case_subtype=document["case_subtype"],
            classification=classification,
        )

    return documents


def main() -> None:
    documents = load_documents()

    print("Embedding 모델을 불러오는 중...")
    model = SentenceTransformer(MODEL_NAME)

    client = chromadb.PersistentClient(path=str(DB_PATH))

    collection = client.get_or_create_collection(
        name=COLLECTION_NAME
    )

    passages = [
        (
            f"passage: "
            f"{document['case_type']} "
            f"{document['case_subtype']} "
            f"{document['title']} "
            f"{document['content']}"
        )
        for document in documents
    ]

    print("문서를 벡터로 변환하는 중...")

    embeddings = model.encode(
        passages,
        normalize_embeddings=True,
    ).tolist()

    metadatas = [
        {
            "title": document["title"],
            "document_type": document["document_type"],
            "case_type": document["case_type"],
            "case_subtype": document["case_subtype"],
        }
        for document in documents
    ]

    collection.upsert(
        ids=[document["id"] for document in documents],
        documents=[document["content"] for document in documents],
        metadatas=metadatas,
        embeddings=embeddings,
    )

    print(f"저장 완료: {len(documents)}개 문서")
    print(f"ChromaDB 위치: {DB_PATH}")


if __name__ == "__main__":
    main()