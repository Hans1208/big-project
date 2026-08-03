from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.ai.forms import recommender
from app.routers.forms import router


app = FastAPI()
app.include_router(router)

client = TestClient(app)


def test_recommend_endpoint_uses_real_local_rag(
    monkeypatch,
):
    # 규칙 기반 후보를 비워서 실제 RAG 후보만 확인한다.
    recommender._mapping_cache = []

    captured = {}

    def fake_ask_gpt(
        analysis,
        candidates,
    ):
        captured["candidates"] = candidates

        first = candidates[0]

        return {
            "recommendations": [
                {
                    "rank": 1,
                    "form_name": first["name"],
                    "reason": (
                        "실제 로컬 RAG 검색 결과를 "
                        "사용한 테스트 추천입니다."
                    ),
                }
            ],
            "reason_if_empty": "",
        }

    # RAG 검색은 실제로 실행하고 GPT 호출만 막는다.
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
            "배우자와 이혼하면서 혼인 중 함께 "
            "모은 재산을 나누고 싶습니다."
        ),
        "extracted_json": {
            "사건개요": (
                "배우자 명의의 아파트와 예금에 "
                "대해 재산분할을 청구하려 합니다."
            )
        },
    }

    response = client.post(
        "/forms/recommend",
        json=payload,
    )

    assert response.status_code == 200

    body = response.json()

    assert body["candidates_count"] >= 1
    assert body["recommendations"]

    candidates = captured["candidates"]

    rag_candidates = [
        candidate
        for candidate in candidates
        if "similarity" in candidate
    ]

    assert len(rag_candidates) >= 1

    assert any(
        keyword in candidate["name"]
        for candidate in rag_candidates
        for keyword in (
            "이혼",
            "재산",
            "분할",
        )
    )
