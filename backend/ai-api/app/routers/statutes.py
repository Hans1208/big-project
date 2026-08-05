"""법령·판례 검색과 추천.

화면(프론트 '법령·판례')은 두 가지를 함께 쓴다.
  · 직접 검색 — 상담원이 검색어를 넣어 조문을 찾는다
  · AI 추천   — 상담 분석 결과를 그대로 질의로 삼아 관련 조문을 올려준다

둘 다 같은 색인(legal_statutes, 2,258개 조문)을 본다. 다른 건 질의를 사람이
만드느냐 분석 결과에서 만드느냐뿐이라, 검색 함수 하나를 두고 질의 생성만
나눈다.

추천 결과에는 유사도와 '왜 이게 나왔는지'를 함께 실어 보낸다. 상담원이
근거 없이 목록만 받으면 검토에 쓸 수가 없다 — 순위만 주는 추천은
"AI가 그렇다니까"밖에 안 된다.
"""
from fastapi import APIRouter, HTTPException

from app.ai.fulltext import build_full_text
from app.ai.statutes.explainer import select_and_explain
from rag.statute_retriever import get_default_statute_retriever, retrieve_statutes

router = APIRouter(prefix="/statutes", tags=["statutes"])

# 검색과 추천은 필요한 개수가 다르다.
#   · 직접 검색 — 상담원이 훑어보며 고르는 자리라 넉넉해야 한다. 5건만 주면
#     찾는 조문이 6위였을 때 "없다"고 결론내게 된다.
#   · AI 추천   — 상위 몇 건만 의미가 있다. 20건을 추천이라고 내밀면 결국
#     상담원이 다시 다 읽어야 해서 추천이 아니다.
SEARCH_TOP_K = 20
RECOMMEND_TOP_K = 5
# 추천에서 검색기에 요구하는 후보 수. 임베딩은 2,258개에서 후보를 좁히는 일은
# 잘하지만 그중 무엇이 맞는지는 못 고른다(실측: 정답이 1·2·3·7·9위에 흩어져
# 있었고, 상위 5건만 잘라 쓰면 그 중 둘을 놓쳤다). 넉넉히 뽑아 판단은
# explainer에 맡긴다. 조문 평균 본문이 175자라 30건이어도 프롬프트는 6천 자
# 안쪽이고, LLM 호출 횟수는 그대로 한 번이다.
RECOMMEND_CANDIDATE_K = 30
# '직접 검색'은 상담원이 검색어를 넣어 찾는 것이라, 우리가 몇 건까지만 보라고
# 자를 이유가 없다 - 찾는 것이 101위였을 때 "없다"고 결론내게 된다. 색인이 가진
# 만큼 다 내주고, 어디까지 볼지는 화면에서 스크롤로 정하게 한다.
#
# 색인 크기(조문 2,289청크 / 판례 342건)보다 크게 잡아 사실상 상한이 없게 둔다.
# 그래도 값을 남겨두는 것은, 잘못된 요청 하나가 서버를 통째로 붙잡는 것을 막기
# 위해서다.
MAX_TOP_K = 3000


def _to_card(row: dict) -> dict:
    """검색 결과 한 건을 화면이 쓰는 모양으로 줄인다.

    색인 레코드는 30개 가까운 키를 담고 있는데(청크 id, 소관부처, 공포번호 등)
    화면에 필요한 건 제목·조문본문·유사도·출처뿐이다. 그대로 넘기면 응답이
    커지기만 하고, 프론트가 어떤 키를 믿어야 할지도 흐려진다."""
    similarity = row.get("similarity")
    return {
        "id": row.get("id"),
        "title": row.get("title") or "",
        "law_name": row.get("law_name") or "",
        "article_label": row.get("article_label") or "",
        "article_title": row.get("article_title") or "",
        "content": row.get("content") or "",
        "effective_date": row.get("article_effective_date")
        or row.get("effective_date")
        or "",
        # 화면에서 "유사도 90%"로 바로 쓸 수 있게 백분율까지 계산해 보낸다.
        # 소수 셋째 자리를 프론트마다 다르게 반올림하면 같은 결과가 화면마다
        # 달라 보인다.
        "similarity": similarity,
        "similarity_percent": (
            round(similarity * 100, 1) if isinstance(similarity, (int, float)) else None
        ),
        "source": "국가법령정보센터",
        "law_id": row.get("law_id") or "",
    }


def _search(query: str, law_id: str | None, top_k: int) -> list:
    query = (query or "").strip()
    if not query:
        raise HTTPException(status_code=400, detail="검색어가 필요합니다")
    top_k = max(1, min(int(top_k or SEARCH_TOP_K), MAX_TOP_K))
    try:
        rows = retrieve_statutes(query=query, law_id=law_id or None, top_k=top_k)
    except Exception as e:  # 색인이 없거나 임베딩 모델 로딩이 실패한 경우
        raise HTTPException(
            status_code=503, detail=f"법령 검색을 사용할 수 없습니다: {type(e).__name__}"
        )

    # 화면에 "유사도 89.9%"를 띄우는데 목록이 87.4% → 89.9% 순이면 고장난 것처럼
    # 보인다. 재순위(rerank_score)는 조문 번호를 직접 검색할 때 정확히 맞히려고
    # 어휘 일치에 가산점을 주는 값이라 유사도와 순서가 어긋난다. 후보를 고르는
    # 일은 재순위에 그대로 맡기고(그게 top_k를 정한다), 보여주는 순서만
    # 화면에 찍히는 숫자와 맞춘다.
    cards = [_to_card(r) for r in rows]
    cards.sort(key=lambda c: c.get("similarity") or 0, reverse=True)
    return cards


@router.post("/search")
def search_statutes(payload: dict):
    """상담원이 직접 넣은 검색어로 조문을 찾는다.

    payload: {query, law_id(선택), top_k(선택)}"""
    return {
        "query": (payload.get("query") or "").strip(),
        "results": _search(payload.get("query"), payload.get("law_id"),
                           payload.get("top_k", SEARCH_TOP_K)),
    }


def _build_query(analysis: dict) -> str:
    """분석 결과에서 검색 질의를 만든다.

    요약을 통째로 넣으면 "상담을 신청하였습니다" 같은 상담기록 말투가 섞여
    엉뚱한 조문이 올라온다. 사건 유형과 사건개요를 앞에 세워 법률 쟁점 쪽으로
    질의를 기울인다."""
    extracted = analysis.get("extracted_json") or {}
    parts = [
        analysis.get("case_subtype") or "",
        analysis.get("case_type") or "",
        extracted.get("사건개요") if isinstance(extracted, dict) else "",
        analysis.get("summary") or "",
    ]
    return " ".join(p for p in parts if p).strip()


@router.post("/recommend")
def recommend_statutes(payload: dict):
    """상담 분석 결과로 관련 조문을 추천한다.

    payload: AI_ANALYSIS 형태 (case_type, case_subtype, summary, extracted_json)

    추천은 후보 제시일 뿐 확정이 아니다 — 어떤 조문을 근거로 쓸지는
    상담원·변호사가 정한다(HITL). 그래서 근거(reason)를 함께 준다."""
    query = _build_query(payload)
    if not query:
        raise HTTPException(
            status_code=400, detail="추천할 근거가 없습니다 (사건유형·요약이 비어 있음)"
        )

    candidates = _search(query, payload.get("law_id"), RECOMMEND_CANDIDATE_K)
    case_label = payload.get("case_subtype") or payload.get("case_type") or "이 사건"
    limit = max(1, min(int(payload.get("top_k") or RECOMMEND_TOP_K), RECOMMEND_CANDIDATE_K))

    # 후보 중 이 상담에 실제로 쓸 조문만 고르고, 왜 관련되는지를 상담 사실에
    # 근거해 한 줄로 붙인다(app/ai/statutes/explainer.py). 유사도 순서를 그대로
    # 내보내면 관련 없는 조문이 상위를 차지한다 — 양육비 상담에서 정답이 9위,
    # 그 위 세 자리를 가족관계증명서 조문이 가져간 적이 있다.
    results = select_and_explain(
        candidates, payload.get("summary") or "", case_label, limit)
    return {"query": query, "results": results}


@router.post("/full-text")
def statute_full_text(payload: dict):
    """카드 하나에 대응하는 조문 본문 전체를 돌려준다.

    payload: {id: 검색 결과 카드의 id(청크 id)}

    색인은 조문을 800자씩 잘라 담는다(rag/chunking.py DEFAULT_CHUNK_SIZE).
    긴 조문은 여러 조각이 되고, 카드에는 검색에 걸린 조각 하나만 실린다 -
    실측에서 가사소송법 제2조가 797자에서, 그것도 항목 중간에서 끊겼다.
    '전문 보기'는 여기서 받은 것을 보여준다."""
    chunk_id = str(payload.get("id") or "").strip()

    if not chunk_id:
        raise HTTPException(status_code=400, detail="id가 필요합니다")

    try:
        store = get_default_statute_retriever().vector_store
        result = build_full_text(store, chunk_id)
    except Exception as e:  # 색인이 없거나 핸들이 깨진 경우
        raise HTTPException(
            status_code=503,
            detail=f"조문 원문을 불러올 수 없습니다: {type(e).__name__}",
        )

    if not result.get("found"):
        raise HTTPException(status_code=404, detail="해당 조문을 찾지 못했습니다")

    return result
