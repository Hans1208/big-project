from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.ai.forms import recommender
from app.routers.forms import router


app = FastAPI()
app.include_router(router)

client = TestClient(app)


def test_recommend_endpoint_uses_local_rag_candidates(
    monkeypatch,
):
    recommender._mapping_cache = []

    captured = {}

    def fake_rag_search(
        query_text,
        top_n=10,
    ):
        captured["query_text"] = query_text
        captured["top_n"] = top_n

        return [
            {
                "tmpltNo": "FORM-001",
                "name": "재산분할 심판청구서",
                "main": "친족",
                "sub": "이혼 및 재산분할청구권",
                "similarity": 0.91,
                "chunk_id": "FORM-001::chunk-0001",
                "source": "forms/FORM-001.hwpx",
            }
        ]

    def fake_ask_gpt(
        analysis,
        candidates,
    ):
        captured["analysis"] = analysis
        captured["candidates"] = candidates

        return {
            "recommendations": [
                {
                    "rank": 1,
                    "form_name": (
                        "재산분할 심판청구서"
                    ),
                    "reason": (
                        "이혼 후 공동재산 분할을 "
                        "요청하고 있기 때문입니다."
                    ),
                }
            ],
            "reason_if_empty": "",
        }

    monkeypatch.setattr(
        recommender,
        "search_rag_candidates",
        fake_rag_search,
    )

    monkeypatch.setattr(
        recommender,
        "_ask_gpt",
        fake_ask_gpt,
    )

    payload = {
        "case_type": "친족",
        "case_subtype": (
            "이혼 및 재산분할청구권"
        ),
        "summary": (
            "이혼 후 혼인 중 형성한 재산을 "
            "분할받고 싶습니다."
        ),
        "extracted_json": {
            "사건개요": (
                "배우자 명의의 아파트와 예금이 "
                "있습니다."
            )
        },
    }

    response = client.post(
        "/forms/recommend",
        json=payload,
    )

    assert response.status_code == 200

    body = response.json()

    assert body["recommendations"][0][
        "form_name"
    ] == "재산분할 심판청구서"

    assert body["candidates_count"] == 1

    assert captured["query_text"] == (
        "이혼 후 혼인 중 형성한 재산을 "
        "분할받고 싶습니다. "
        "배우자 명의의 아파트와 예금이 "
        "있습니다."
    )

    assert captured["top_n"] == (
        recommender.EMBEDDING_TOP_N
    )

    assert captured["candidates"][0][
        "tmpltNo"
    ] == "FORM-001"
