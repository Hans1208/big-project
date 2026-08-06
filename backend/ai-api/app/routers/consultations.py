"""유사 상담사례 검색과 추천.

법령·판례 탭과 같은 자리에서 쓰는 세 번째 자료다. 다른 점은 '무엇을 근거로
삼느냐'뿐이다 — 법령은 조문, 판례는 법원 판단, 여기는 **공단이 실제로 답변한
상담 기록**이다. 같은 질문을 이미 받아 답한 적이 있다면 그 답이 가장 빠른
길잡이가 된다.

색인은 가사법 상담 1,664건(1,996 청크). 원본은 공단이 공개한 기본상담·
사례상담 Q&A 4종(10,826행)에서 가사 분야만 추린 것이다.

라우터 구조는 statutes.py / precedents.py와 일부러 똑같이 맞췄다. 화면이 탭마다
다른 응답 모양을 알 필요가 없도록, 카드 키(id/title/content/similarity_percent/
source/effective_date)를 세 탭이 공유한다.

검색 계층(app/ai/consultations/*, rag/consultation_retriever.py)은 이미 있는 것을
그대로 쓴다. 다만 retriever를 직접 부른다 — service 층의 find_related_consultations는
예외를 삼켜 빈 목록을 돌려주도록 되어 있는데(분석 파이프라인에서는 상담사례를
못 찾아도 분석이 멈추면 안 되므로 맞는 선택이다), 검색 화면에서는 "색인이 죽었다"와
"결과가 없다"가 같아 보이면 안 된다. 여기서는 실패를 503으로 드러낸다.
"""
from fastapi import APIRouter, HTTPException

from app.ai.consultations.rag_results import (
    convert_rag_results_to_consultations,
)
from app.ai.fulltext import build_full_text
from rag.consultation_retriever import (
    get_default_consultation_retriever,
    retrieve_consultations,
)

router = APIRouter(prefix="/consultations", tags=["consultations"])

# 법령·판례와 같은 이유로 검색과 추천의 건수를 다르게 둔다(statutes.py 주석 참고).
SEARCH_TOP_K = 20
RECOMMEND_TOP_K = 3
# 색인 크기(1,996 청크)보다 크게 잡아 사실상 상한을 두지 않는다. 값을 남기는 것은
# 잘못된 요청 하나가 서버를 오래 붙잡는 것을 막기 위해서다.
MAX_TOP_K = 3000

# 이 상담들은 공단이 공개한 상담 Q&A다. 화면에 출처를 밝혀야 상담원이 "누가 한
# 답변인지"를 알고 인용 여부를 판단할 수 있다.
SOURCE_LABEL = "대한법률구조공단 상담사례"

# 상담 기록은 기본상담(자주 묻는 질문에 대한 표준 답변)과 사례상담(실제 사건에
# 대한 답변)이 섞여 있다. 둘은 무게가 달라서 화면에 구분해 보여준다.
SOURCE_TYPE_LABELS = {
    "basic": "기본상담",
    "case": "사례상담",
}


def _to_card(row: dict) -> dict:
    """검색 결과 한 건을 화면이 쓰는 모양으로 줄인다.

    제목 자리에는 '질문'이 들어간다. 상담 기록에는 판례처럼 붙은 사건명이 없고,
    상담원이 목록에서 고를 때 실제로 보는 것도 "이 사람이 뭘 물었나"이기 때문이다.
    본문 자리에는 답변이 들어간다."""
    similarity = row.get("similarity")
    source_type = row.get("source_type") or ""
    return {
        "id": row.get("chunk_id") or "",
        "consultation_id": row.get("consultation_id") or "",
        "title": row.get("question") or "",
        "content": row.get("answer_excerpt") or "",
        "similarity": similarity,
        # 화면에서 "유사도 90%"로 바로 쓸 수 있게 백분율까지 계산해 보낸다
        # (법령·판례와 같은 이유 — 반올림을 프론트마다 다르게 하면 안 된다).
        "similarity_percent": (
            round(similarity * 100, 1) if isinstance(similarity, (int, float)) else None
        ),
        "source": SOURCE_LABEL,
        "source_type": source_type,
        "source_type_label": SOURCE_TYPE_LABELS.get(source_type, ""),
        # 법률분류 경로("가사 > 이혼 > 재산분할"). 카드에서 이 상담이 어느 갈래인지
        # 알려 준다. 법령의 law_name, 판례의 court_level에 해당하는 자리다.
        "legal_path": row.get("legal_path") or "",
        "service_category": row.get("service_category") or "",
        # 법령은 시행일, 판례는 선고일이 오는 자리. 상담은 자료 기준일이다.
        "effective_date": row.get("source_date") or "",
    }


def _assert_index_ready() -> None:
    """색인이 살아 있는지 먼저 확인한다.

    ConsultationRetriever.retrieve()는 임베딩·검색이 실패해도 예외를 올리지 않고
    빈 목록을 돌려준다. 분석 파이프라인에서는 맞는 선택이지만(상담사례를 못 찾아도
    분석은 끝나야 한다), 검색 화면에서는 그 때문에 "색인이 죽었다"와 "결과가 없다"가
    똑같이 '0건'으로 보인다. 실제로 판례 쪽에서 Chroma 핸들이 깨졌을 때
    "판례를 찾지 못했습니다"만 뜨고 원인을 못 찾은 적이 있다.

    그래서 검색을 부르기 전에 색인을 한 번 두드려 본다. 여기서 실패하거나 0건이면
    검색 결과가 아니라 설비 문제이므로 503으로 드러낸다. retrieve()를 고치지 않고
    분간할 수 있는 가장 싼 방법이다."""
    try:
        stored = get_default_consultation_retriever().vector_store.count()
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=f"상담사례 색인을 열 수 없습니다: {type(e).__name__}",
        )
    if not stored:
        raise HTTPException(
            status_code=503,
            detail=(
                "상담사례 색인이 비어 있습니다 "
                "(rag.build_consultation_index를 먼저 실행해 주세요)"
            ),
        )


def _search(query: str, top_k: int) -> list:
    query = (query or "").strip()
    if not query:
        raise HTTPException(status_code=400, detail="검색어가 필요합니다")
    _assert_index_ready()
    top_k = max(1, min(int(top_k or SEARCH_TOP_K), MAX_TOP_K))
    try:
        rows = retrieve_consultations(query=query, top_k=top_k)
    except Exception as e:  # retrieve()가 삼키지 못한 예외(잘못된 인자 등)
        raise HTTPException(
            status_code=503,
            detail=f"상담사례 검색을 사용할 수 없습니다: {type(e).__name__}",
        )

    # 같은 상담이 여러 청크로 걸리면 한 건으로 합친다. 그 처리는 이미
    # app/ai/consultations/rag_results.py가 하고 있으므로 그대로 쓴다.
    converted = convert_rag_results_to_consultations(rows)

    # 화면에 찍히는 유사도 순서와 목록 순서를 맞춘다. 재순위(rerank_score)는
    # 주제 신호에 가산점을 주는 값이라 유사도와 순서가 어긋난다 — 후보를 고르는
    # 일은 재순위에 맡기고, 보여주는 순서만 화면 숫자와 맞춘다(statutes.py와 같은 처리).
    cards = [_to_card(r) for r in converted]
    cards.sort(key=lambda c: c.get("similarity") or 0, reverse=True)
    return cards


@router.post("/search")
def search_consultations(payload: dict):
    """상담원이 직접 넣은 검색어로 유사 상담사례를 찾는다.

    payload: {query, top_k(선택)}"""
    return {
        "query": (payload.get("query") or "").strip(),
        "results": _search(payload.get("query"), payload.get("top_k", SEARCH_TOP_K)),
    }


def _build_query(analysis: dict) -> str:
    """분석 결과에서 검색 질의를 만든다.

    법령·판례와 달리 사건유형을 앞세우지 않고 요약을 그대로 쓴다. 상담사례
    색인은 '내담자가 한 말'로 이루어져 있어서, 질의도 사람 말투에 가까울수록
    잘 걸린다 — 검색기 쪽에 "아이를보지못 → 면접교섭" 같은 주제 신호가
    들어 있는 것도 같은 이유다(rag/consultation_retriever.py TOPIC_SIGNALS).
    사건유형은 뒤에 덧붙여 갈래만 좁힌다."""
    extracted = analysis.get("extracted_json") or {}
    parts = [
        analysis.get("summary") or "",
        extracted.get("사건개요") if isinstance(extracted, dict) else "",
        analysis.get("case_subtype") or "",
        analysis.get("case_type") or "",
    ]
    return " ".join(p for p in parts if p).strip()


@router.post("/recommend")
def recommend_consultations(payload: dict):
    """상담 분석 결과로 유사 상담사례를 추천한다.

    payload: AI_ANALYSIS 형태 (case_type, case_subtype, summary, extracted_json)

    법령·판례 추천과 달리 LLM 설명(explainer)을 거치지 않는다. 조문·판례는
    "왜 이게 이 사건에 걸리는가"를 따로 설명해 주지 않으면 상담원이 판단할 수
    없지만, 상담사례는 질문 자체가 그 설명이다 — 내 사건과 비슷한지는 질문 한 줄만
    읽으면 바로 안다. 설명을 덧붙이려고 LLM을 한 번 더 부르면 응답만 느려진다.

    추천은 후보 제시일 뿐 확정이 아니다(HITL). 실제로 어떤 상담을 참고할지는
    상담원이 정한다."""
    query = _build_query(payload)
    if not query:
        raise HTTPException(
            status_code=400, detail="추천할 근거가 없습니다 (요약·사건유형이 비어 있음)"
        )

    limit = max(1, min(int(payload.get("top_k") or RECOMMEND_TOP_K), MAX_TOP_K))
    return {"query": query, "results": _search(query, limit)}


@router.post("/full-text")
def consultation_full_text(payload: dict):
    """카드 하나에 대응하는 상담 답변 전체를 돌려준다.

    payload: {id: 검색 결과 카드의 id(청크 id)}

    목록 카드의 본문은 답변을 잘라낸 발췌다(rag_results.py _excerpt). 답변이 긴
    상담은 결론이 뒤에 있어서, 발췌만 읽고 판단하면 반대로 이해할 수 있다.
    법령·판례의 '전문 보기'와 같은 이유로 열어 둔다."""
    chunk_id = str(payload.get("id") or "").strip()

    if not chunk_id:
        raise HTTPException(status_code=400, detail="id가 필요합니다")

    try:
        store = get_default_consultation_retriever().vector_store
        result = build_full_text(store, chunk_id)
    except Exception as e:  # 색인이 없거나 핸들이 깨진 경우
        raise HTTPException(
            status_code=503,
            detail=f"상담 답변 원문을 불러올 수 없습니다: {type(e).__name__}",
        )

    if not result.get("found"):
        raise HTTPException(status_code=404, detail="해당 상담사례를 찾지 못했습니다")

    return result
