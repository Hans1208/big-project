from app.ai.forms.rag_candidates import (
    search_rag_candidates,
)


def test_search_rag_candidates_forwards_classification():
    captured = {}

    def fake_retrieve(
        query,
        case_type=None,
        case_subtype=None,
        classification_confidence=None,
        top_k=3,
    ):
        captured["query"] = query
        captured["case_type"] = case_type
        captured["case_subtype"] = case_subtype
        captured["classification_confidence"] = (
            classification_confidence
        )
        captured["top_k"] = top_k

        return [
            {
                "document_id": "I001000051",
                "title": "개명허가신청서",
                "case_type": "가족관계등록",
                "case_subtype": "성본창설과 개명",
                "similarity": 0.91,
                "chunk_id": (
                    "I001000051::chunk-0001"
                ),
                "source": (
                    "forms/I001000051.hwpx"
                ),
            }
        ]

    results = search_rag_candidates(
        query_text=(
            "현재 이름 때문에 생활에 불편이 커서 "
            "개명허가를 신청하고 싶습니다."
        ),
        case_type="가족관계등록",
        case_subtype="성본창설과 개명",
        classification_confidence=0.95,
        top_n=3,
        retrieve=fake_retrieve,
    )

    assert captured == {
        "query": (
            "현재 이름 때문에 생활에 불편이 커서 "
            "개명허가를 신청하고 싶습니다."
        ),
        "case_type": "가족관계등록",
        "case_subtype": "성본창설과 개명",
        "classification_confidence": 0.95,
        "top_k": 3,
    }

    assert results[0]["tmpltNo"] == "I001000051"
    assert results[0]["name"] == "개명허가신청서"
