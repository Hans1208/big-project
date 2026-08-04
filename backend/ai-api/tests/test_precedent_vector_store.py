from rag import config
from rag.vector_store import ChromaVectorStore


def _chunk():
    return {
        "document_id": "precedent:300001:holding",
        "chunk_id": (
            "precedent:300001:holding::chunk-0000"
        ),
        "chunk_index": 0,
        "document_type": "legal_precedent",
        "title": "재산분할 등 [판시사항]",
        "content": "재산분할 대상과 기준시점을 판단한다.",
        "source": "law_api:prec:300001",
        "precedent_id": "300001",
        "case_name": "재산분할 등",
        "case_number": "2023드합12345",
        "decision_date": "20240115",
        "decision": "선고",
        "court_name": "서울가정법원",
        "court_type_code": "400202",
        "court_level": "LOWER",
        "case_type_name": "가사",
        "case_type_code": "400106",
        "decision_type": "판결",
        "holding": "재산분할 대상과 기준시점",
        "summary": "혼인 중 형성한 재산을 분할한다.",
        "referenced_statutes": "민법 제839조의2",
        "referenced_precedents": "대법원 2020므0000",
        "matched_searches": [
            "keyword:title:재산분할:lower",
            "law:민법:재산분할:lower",
        ],
        "section_type": "holding",
        "section_label": "판시사항",
    }


def test_precedent_collection_name_is_separate():
    assert (
        config.LEGAL_PRECEDENTS_COLLECTION_NAME
        == "legal_precedents"
    )


def test_vector_store_preserves_precedent_metadata(
    tmp_path,
):
    store = ChromaVectorStore(
        persist_directory=tmp_path / "chroma",
        collection_name="legal_precedents",
    )

    chunk = _chunk()

    store.upsert_documents(
        documents=[chunk],
        embeddings=[[1.0, 0.0]],
    )

    result = store.search(
        query_embedding=[1.0, 0.0],
        top_k=1,
        where={
            "court_level": "LOWER",
        },
    )

    assert len(result) == 1

    stored = result[0]

    assert stored["precedent_id"] == "300001"
    assert stored["case_name"] == "재산분할 등"
    assert stored["case_number"] == "2023드합12345"
    assert stored["court_name"] == "서울가정법원"
    assert stored["court_level"] == "LOWER"
    assert stored["section_type"] == "holding"
    assert stored["referenced_statutes"] == (
        "민법 제839조의2"
    )
    assert stored["matched_searches"] == (
        "keyword:title:재산분할:lower"
        " | law:민법:재산분할:lower"
    )