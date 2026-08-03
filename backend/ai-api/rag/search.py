from pathlib import Path
from typing import Optional

import chromadb
from sentence_transformers import SentenceTransformer

from classification import build_where_filter


BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR.parent / "storage" / "chroma"

MODEL_NAME = "intfloat/multilingual-e5-small"
COLLECTION_NAME = "legal_documents"
TOP_K = 3

HIGH_CONFIDENCE = 0.75
MEDIUM_CONFIDENCE = 0.50


def has_results(results: dict) -> bool:
    """검색 결과가 한 건 이상인지 확인한다."""
    return bool(results.get("ids") and results["ids"][0])


def build_filter_chain(
    case_type: Optional[str] = None,
    case_subtype: Optional[str] = None,
    classification_confidence: Optional[float] = None,
) -> list[Optional[dict]]:
    """
    분류 신뢰도에 따라 검색 필터 적용 순서를 만든다.

    0.75 이상:
        대분류+소분류 → 대분류 → 전체 검색
    0.50 이상:
        대분류 → 전체 검색
    0.50 미만 또는 분류값 없음:
        전체 검색
    """
    if classification_confidence is None:
        return [None]

    if (
        classification_confidence >= HIGH_CONFIDENCE
        and case_type
        and case_subtype
    ):
        return [
            build_where_filter(
                case_type=case_type,
                case_subtype=case_subtype,
            ),
            build_where_filter(case_type=case_type),
            None,
        ]

    if (
        classification_confidence >= MEDIUM_CONFIDENCE
        and case_type
    ):
        return [
            build_where_filter(case_type=case_type),
            None,
        ]

    return [None]


def run_query(
    collection,
    query_embedding: list[list[float]],
    where_filter: Optional[dict] = None,
) -> dict:
    """ChromaDB 벡터 검색을 실행한다."""
    document_count = collection.count()

    if document_count == 0:
        return {"ids": [[]]}

    query_arguments = {
        "query_embeddings": query_embedding,
        "n_results": min(TOP_K, document_count),
        "include": [
            "documents",
            "metadatas",
            "distances",
        ],
    }

    if where_filter is not None:
        query_arguments["where"] = where_filter

    return collection.query(**query_arguments)


def search_documents(
    query: str,
    model: SentenceTransformer,
    collection,
    case_type: Optional[str] = None,
    case_subtype: Optional[str] = None,
    classification_confidence: Optional[float] = None,
) -> dict:
    """
    상담 내용으로 관련 법률 문서를 검색한다.

    현재 CLI에서는 query만 전달하여 전체 문서를 검색한다.
    이후 AI_ANALYSIS 연동 시 사건 분류값과 신뢰도를 함께 전달한다.
    """
    query = query.strip()

    if not query:
        raise ValueError("검색할 상담 내용이 비어 있습니다.")

    query_embedding = model.encode(
        [f"query: {query}"],
        normalize_embeddings=True,
    ).tolist()

    filter_chain = build_filter_chain(
        case_type=case_type,
        case_subtype=case_subtype,
        classification_confidence=classification_confidence,
    )

    for where_filter in filter_chain:
        results = run_query(
            collection=collection,
            query_embedding=query_embedding,
            where_filter=where_filter,
        )

        if has_results(results):
            return results

    return {"ids": [[]]}


def print_results(results: dict) -> None:
    """검색 결과를 터미널에 출력한다."""
    if not has_results(results):
        print("\n검색된 문서가 없습니다.")
        return

    print("\n=== 검색 결과 ===")

    result_ids = results["ids"][0]
    result_documents = results["documents"][0]
    result_metadatas = results["metadatas"][0]
    result_distances = results["distances"][0]

    for rank, document_id in enumerate(result_ids, start=1):
        metadata = result_metadatas[rank - 1]
        document = result_documents[rank - 1]
        distance = result_distances[rank - 1]

        print(f"\n[{rank}위]")
        print(f"문서 ID: {document_id}")
        print(f"제목: {metadata.get('title', '-')}")
        print(f"대분류: {metadata.get('case_type', '-')}")
        print(f"소분류: {metadata.get('case_subtype', '-')}")
        print(f"문서 유형: {metadata.get('document_type', '-')}")
        print(f"거리값: {distance:.4f}")
        print(f"내용: {document}")


def main() -> None:
    print("Embedding 모델을 불러오는 중...")
    model = SentenceTransformer(MODEL_NAME)

    client = chromadb.PersistentClient(
        path=str(DB_PATH)
    )

    try:
        collection = client.get_collection(
            name=COLLECTION_NAME
        )
    except Exception as error:
        raise RuntimeError(
            "저장된 문서가 없습니다. "
            "먼저 build_index.py를 실행하세요."
        ) from error

    # 사용자에게는 상담 내용만 입력받는다.
    query = input("\n상담 내용을 입력하세요: ").strip()

    try:
        results = search_documents(
            query=query,
            model=model,
            collection=collection,
        )
    except ValueError as error:
        print(f"입력 오류: {error}")
        return

    print_results(results)


if __name__ == "__main__":
    main()