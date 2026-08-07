"""판례 검색과 추천.

화면('법령·판례' 자료실)의 판례 탭이 법령 탭과 같은 두 가지를 쓴다.
  · 직접 검색 — 상담원이 검색어를 넣어 판례를 찾는다
  · AI 추천   — 상담 분석 결과를 질의로 삼아 관련 판례를 올려준다

법령 쪽(routers/statutes.py)과 같은 구조로 맞춘다. 화면이 두 탭을 같은
카드로 그리기 때문에 응답 모양도 맞춰야 한다 — 다르게 만들면 프론트가 탭마다
다른 키를 알아야 한다.

판례에만 있는 사정이 둘 있다.

  1. 색인은 판례 한 건을 여러 청크(판시사항·요약·전문)로 쪼개 담는다. 그대로
     내보내면 같은 사건이 목록을 채운다. search_precedent_rag가 사건 단위로
     중복을 걷어내지만, 그건 '받아온 청크 안에서' 걷어내는 것이라 청크를
     넉넉히 받아야 원하는 건수가 남는다.
  2. 판례는 사실관계가 조금만 달라도 결론이 뒤집힌다. 유사도 순위만으로는
     "비슷해 보이는데 결론이 반대인 사건"이 걸러지지 않아, 추천에는 조문과
     같이 선별 단계를 둔다(app/ai/precedents/explainer.py).
"""
from fastapi import APIRouter, HTTPException

from app.ai.fulltext import build_full_text
from app.ai.precedents.explainer import select_and_explain
from app.ai.precedents.rag_results import search_precedent_rag
from rag.precedent_retriever import get_default_precedent_retriever

router = APIRouter(prefix="/precedents", tags=["precedents"])

# 법령 쪽과 같은 이유로 검색과 추천의 건수가 다르다(statutes.py 주석 참고).
SEARCH_TOP_K = 20
RECOMMEND_TOP_K = 5
RECOMMEND_CANDIDATE_K = 30
# Cap direct searches so one oversized request cannot monopolize the server.
# The normal default remains 20; only excessive requests are reduced.
MAX_TOP_K = 100

# 사건 단위 중복 제거로 줄어드는 몫을 미리 더 받는다. 한 사건이 판시사항·요약·
# 전문으로 서너 청크가 되므로, 청크를 그만큼 더 받아야 사건 수가 채워진다.
# 색인 실측이 판례 342건 / 청크 3,480개라 사건당 평균 10청크지만, 상위권은
# 여러 사건이 섞이므로 3배로 잡는다. 모자라면 그만큼만 나가고 화면은 뜬다.
CHUNK_OVERFETCH = 3


def _card_title(row: dict) -> str:
    """목록에서 판례를 구별할 수 있는 제목.

    사건명만 쓰면 안 된다. 판례의 사건명은 청구 종류만 적혀 있어 서로 다른
    사건이 같은 이름을 갖는다 — "양육비를 못 받고 있다"로 검색하면 법원도
    선고일도 사건번호도 다른 판례 셋이 전부 "양육비"로 나온다. 상담원 눈에는
    같은 것이 세 번 뜬 것으로 보이고, 어느 것을 열어봐야 할지 알 수 없다.

    사건번호를 붙인다 — 법조인이 판례를 특정할 때 쓰는 값이고, 이것만으로
    법원과 연도까지 읽힌다(2018브1057).
    """
    case_name = (row.get("case_name") or "").strip()
    case_number = (row.get("case_number") or "").strip()
    if case_name and case_number:
        return f"{case_name} [{case_number}]"
    return case_name or case_number or (row.get("citation") or "")


def _to_card(row: dict) -> dict:
    """검색 결과 한 건을 화면이 쓰는 모양으로 줄인다.

    법령 카드와 같은 키(id/title/content/effective_date/similarity_percent/
    source)를 쓰고, 판례에만 있는 값은 뒤에 덧붙인다. 화면이 탭마다 다른 키를
    알 필요가 없어야 한다.

    본문은 판시사항을 먼저 쓴다 — 전문은 길어서 목록에서 훑을 수가 없고,
    상담원이 이 판례를 볼지 말지 정하는 근거는 판시사항이다."""
    similarity = row.get("similarity")
    citation = row.get("citation") or ""
    case_number = row.get("case_number") or ""
    return {
        "id": row.get("chunk_id") or row.get("precedent_id") or "",
        "title": _card_title(row),
        "content": (row.get("holding") or row.get("summary")
                    or row.get("content") or ""),
        # 화면의 법령 카드가 '시행일'을 쓰는 자리에 선고일을 넣는다.
        "effective_date": row.get("decision_date") or "",
        "similarity": similarity,
        "similarity_percent": (
            round(similarity * 100, 1)
            if isinstance(similarity, (int, float)) else None
        ),
        "source": row.get("court_name") or "국가법령정보센터",
        # 판례 고유 값. 사건번호가 없으면 어느 판례인지 특정할 수 없다.
        "precedent_id": row.get("precedent_id") or "",
        "case_name": row.get("case_name") or "",
        "case_number": case_number,
        "court_name": row.get("court_name") or "",
        "court_level": row.get("court_level") or "",
        "decision_date": row.get("decision_date") or "",
        "citation": citation,
        "holding": row.get("holding") or "",
        "summary": row.get("summary") or "",
        "referenced_statutes": row.get("referenced_statutes") or "",
    }


def _search(query: str, court_level: str | None, top_k: int) -> list:
    query = (query or "").strip()
    if not query:
        raise HTTPException(status_code=400, detail="검색어가 필요합니다")
    top_k = max(1, min(int(top_k or SEARCH_TOP_K), MAX_TOP_K))
    try:
        rows = search_precedent_rag(
            query_text=query,
            top_n=top_k * CHUNK_OVERFETCH,
            court_level=court_level or None,
        )
    except Exception as e:  # 색인이 없거나 임베딩 모델 로딩이 실패한 경우
        raise HTTPException(
            status_code=503,
            detail=f"판례 검색을 사용할 수 없습니다: {type(e).__name__}",
        )

    cards = [_to_card(r) for r in rows]
    # 화면에 찍히는 유사도와 목록 순서를 맞춘다(statutes.py와 같은 이유).
    cards.sort(key=lambda c: c.get("similarity") or 0, reverse=True)
    return cards[:top_k]


@router.post("/search")
def search_precedents(payload: dict):
    """상담원이 직접 넣은 검색어로 판례를 찾는다.

    payload: {query, court_level(선택: 'SUPREME'|'LOWER'), top_k(선택)}"""
    return {
        "query": (payload.get("query") or "").strip(),
        "results": _search(payload.get("query"), payload.get("court_level"),
                           payload.get("top_k", SEARCH_TOP_K)),
    }


def _build_query(analysis: dict) -> str:
    """분석 결과에서 검색 질의를 만든다.

    법령 쪽과 같은 이유로 사건유형·사건개요를 앞에 세운다 — 요약을 통째로
    넣으면 "상담을 신청하였습니다" 같은 상담기록 말투가 섞여 엉뚱한 판례가
    올라온다."""
    extracted = analysis.get("extracted_json") or {}
    parts = [
        analysis.get("case_subtype") or "",
        analysis.get("case_type") or "",
        extracted.get("사건개요") if isinstance(extracted, dict) else "",
        analysis.get("summary") or "",
    ]
    return " ".join(p for p in parts if p).strip()


@router.post("/recommend")
def recommend_precedents(payload: dict):
    """상담 분석 결과로 관련 판례를 추천한다.

    payload: AI_ANALYSIS 형태 (case_type, case_subtype, summary, extracted_json)

    추천은 후보 제시일 뿐 확정이 아니다 — 어떤 판례를 근거로 쓸지는
    상담원·변호사가 정한다(HITL). 그래서 근거(reason)를 함께 준다."""
    query = _build_query(payload)
    if not query:
        raise HTTPException(
            status_code=400,
            detail="추천할 근거가 없습니다 (사건유형·요약이 비어 있음)",
        )

    candidates = _search(query, payload.get("court_level"),
                         RECOMMEND_CANDIDATE_K)
    case_label = payload.get("case_subtype") or payload.get("case_type") or "이 사건"
    limit = max(1, min(int(payload.get("top_k") or RECOMMEND_TOP_K),
                       RECOMMEND_CANDIDATE_K))

    results = select_and_explain(
        candidates, payload.get("summary") or "", case_label, limit)
    return {"query": query, "results": results}


# 판례 한 건은 판시사항/판결요지/판례내용이 각각 별개 문서로 색인된다
# (rag/precedent_documents.py SECTION_FIELDS). '전문'은 이 중 판례내용이다.
# 카드가 판시사항에서 걸렸다면 그 청크의 document_id로는 판시사항밖에 못 모아
# 오므로, 사건 번호로 판례내용 문서를 직접 지목한다.
PRECEDENT_FULL_TEXT_SECTION = "full_text"
PRECEDENT_SECTION_FALLBACKS = ("full_text", "summary", "holding")


@router.post("/full-text")
def precedent_full_text(payload: dict):
    """카드 하나에 대응하는 판례 본문 전체를 돌려준다.

    payload: {precedent_id(우선), id: 카드의 청크 id}

    목록 카드는 검색에 걸린 청크 하나만 싣는다. 판례 한 건이 열 조각쯤으로
    쪼개져 있어, 그 조각이 문장 중간에서 시작하거나 끝나는 일이 흔하다
    (실측: 2022느단5199가 chunk-0002만 걸려 "비율에 따라"로 시작했다).
    '전문 보기'는 여기서 받은 것을 보여준다."""
    precedent_id = str(payload.get("precedent_id") or "").strip()
    chunk_id = str(payload.get("id") or "").strip()

    if not precedent_id and not chunk_id:
        raise HTTPException(status_code=400, detail="precedent_id 또는 id가 필요합니다")

    try:
        store = get_default_precedent_retriever().vector_store

        result = None
        if precedent_id:
            # 판례내용이 없는 사건도 있다(요지만 공개된 경우). 있는 것 중
            # 가장 온전한 구획으로 내려간다.
            for section in PRECEDENT_SECTION_FALLBACKS:
                found = build_full_text(
                    store, f"precedent:{precedent_id}:{section}")
                if found.get("found"):
                    result = found
                    break

        if result is None and chunk_id:
            result = build_full_text(store, chunk_id)
    except Exception as e:  # 색인이 없거나 핸들이 깨진 경우
        raise HTTPException(
            status_code=503,
            detail=f"판례 원문을 불러올 수 없습니다: {type(e).__name__}",
        )

    if not result or not result.get("found"):
        raise HTTPException(status_code=404, detail="해당 판례를 찾지 못했습니다")

    return result
