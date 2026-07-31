# ai/forms/recommender.py — 서식 추천 모듈
#
# 역할: AI 분석 결과(구조화 JSON) → 추천 서식 목록(recommended_forms_json)
# 사용:
#   from app.ai.forms.recommender import recommend
#   result = recommend(analysis)   # {"recommendations": [...], "candidates_count": N}
#
# FastAPI 연결 예:
#   POST /recommend-forms  → recommend(body)

import json
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

from app.ai.forms.rag_candidates import search_rag_candidates

load_dotenv()
_client = None


def _get_openai_client():
    global _client

    if _client is None:
        _client = OpenAI()

    return _client

EMBEDDING_TOP_N = 10

# 서식 매핑 (helplaw24 공식 분류). ai-api 루트에 위치.
MAPPING_FILE = Path(__file__).resolve().parent.parent.parent.parent / "helplaw24_서식_카테고리_매핑.json"

_mapping_cache = None
def _load_mapping():
    global _mapping_cache
    if _mapping_cache is None:
        _mapping_cache = json.load(open(MAPPING_FILE, encoding="utf-8"))
    return _mapping_cache


# MVP 범위: 서식_hwpx/에 실제로 변환돼 있는 대분류만. helplaw24 매핑 JSON엔
# 이 밖의 대분류(민사소송·민사집행·노동 등 2,146개 전체)도 들어있어서,
# 범위를 안 좁히면 실제 파일이 없는 서식을 후보로 잡을 수 있다.
MVP_CATEGORIES = {"친족", "상속", "가사소송", "가족관계등록"}


def get_candidates(case_type: str, case_subtype: str = None, query_text: str = None) -> list:
    """대분류/소분류로 서식 후보를 좁힌다 (규칙 기반 + 임베딩 검색 보강).

    helplaw24 분류 체계의 main/sub는 항상 주제별로 직관적이지 않다
    (예: "한정승인" 서식이 main=가사소송/sub="라,마류 가사비송"으로 분류돼
    있어, case_type="상속"만으로는 후보에 아예 못 들어옴). main 카테고리
    매칭에 case_subtype 키워드가 서식명에 직접 포함된 것도 함께 후보에
    넣어 이런 분류 경계 문제를 보완한다 — 단, MVP 대분류 안으로만 제한해
    실제 파일이 없는 서식(민사소송·민사집행 등)이 섞이지 않게 한다.

    query_text(상담 요약 등)가 주어지면, 사전계산된 서식 임베딩과의 코사인
    유사도 상위 N개도 후보에 합친다 — 규칙 기반 키워드 매칭이 놓치는
    의미적으로 유사한 서식(동의어·다른 표현)을 보완하기 위함. 임베딩 캐시가
    없으면(빌드 스크립트 미실행) 조용히 건너뛴다."""
    mapping = _load_mapping()
    candidates, seen = [], set()

    def _add(rows):
        for m in rows:
            key = m.get("tmpltNo") or m["name"]
            if key not in seen:
                seen.add(key)
                candidates.append(m)

    if case_subtype:
        _add([m for m in mapping if m["sub"] == case_subtype and m["main"] in MVP_CATEGORIES])

    _add([m for m in mapping if m["main"] == case_type])

    if case_subtype and len(case_subtype) >= 2:
        _add([m for m in mapping
              if case_subtype in m["name"] and m["main"] in MVP_CATEGORIES])

    if query_text:
        _add(
            search_rag_candidates(
                query_text=query_text,
                top_n=EMBEDDING_TOP_N,
                case_type=case_type,
                case_subtype=case_subtype,
            )
        )

    return candidates


RECOMMEND_PROMPT = """너는 법률구조공단 상담을 보조하는 서식 추천 도구다.
상담 분석 결과(사건요약, 추출정보)와 서식 후보 목록을 보고,
이 민원인에게 지금 필요한 서식을 우선순위로 추천한다.

규칙:
1. 반드시 후보 목록에 있는 서식명만 추천한다. 새로 지어내지 않는다.
2. 최대 3개까지, 상황에 가장 맞는 순서로.
3. 각 서식마다 "이 상담의 어떤 사실 때문에 이 서식인지" 근거를
   summary/extracted의 구체적 내용을 인용해 한 문장으로 쓴다.
4. 후보 중 적합한 것이 없으면 recommendations를 빈 배열로 하고
   reason_if_empty에 이유를 쓴다.

출력은 JSON만:
{
  "recommendations": [
    {"rank": 1, "form_name": "서식명 그대로", "reason": "근거 한 문장"},
    {"rank": 2, ...}
  ],
  "reason_if_empty": ""
}"""


def _all_mvp_candidates() -> list:
    """MVP 4개 대분류 전체(약 370여 개) — case_type 좁히기가 어긋났을 때의
    최후 폴백 범위."""
    mapping = _load_mapping()
    return [m for m in mapping if m["main"] in MVP_CATEGORIES]


def _ask_gpt(analysis: dict, candidates: list) -> dict:
    user_msg = (
        f"[상담 분석 결과]\n"
        f"사건유형: {analysis.get('case_type')} > {analysis.get('case_subtype')}\n"
        f"요약: {analysis.get('summary')}\n"
        f"추출정보: {json.dumps(analysis.get('extracted_json', {}), ensure_ascii=False)}\n\n"
        f"[서식 후보 목록]\n" + "\n".join(f"- {c['name']}" for c in candidates)
    )
    resp = _get_openai_client().chat.completions.create(
        model="gpt-4.1-mini",
        messages=[
            {"role": "system", "content": RECOMMEND_PROMPT},
            {"role": "user", "content": user_msg},
        ],
        response_format={"type": "json_object"},
        temperature=0,
    )
    return json.loads(resp.choices[0].message.content)


def recommend(analysis: dict) -> dict:
    """분석 결과를 받아 서식을 추천한다.

    analysis 필수 키: case_type, case_subtype, summary, extracted_json
    반환: {"recommendations": [...], "reason_if_empty": "", "candidates_count": N}

    1차로 case_type/case_subtype 기반 후보 + summary/사건개요 임베딩 검색
    후보를 합쳐 시도한다. 결과가 비면(예: "한정승인" 상담이 case_type="상속"
    으로 분류됐는데, 실제 서식은 "가사소송>라,마류 가사비송"에 있는 것처럼
    helplaw24 분류 체계와 실제 서식 위치가 어긋나는 경우) MVP 전체 범위로
    넓혀 한 번 더 시도한다. 분석 에이전트가 서식 분류 체계까지 알 필요는
    없도록, 이 보정은 전적으로 여기(서식 추천 모듈)에서 처리한다."""
    query_text = " ".join(filter(None, [
        analysis.get("summary"),
        analysis.get("extracted_json", {}).get("사건개요"),
    ]))
    candidates = get_candidates(analysis.get("case_type"), analysis.get("case_subtype"), query_text)
    if not candidates:
        return {"recommendations": [], "reason_if_empty": "해당 유형의 서식 후보가 없습니다.",
                "candidates_count": 0}

    result = _ask_gpt(analysis, candidates)
    result["candidates_count"] = len(candidates)

    if not result.get("recommendations"):
        broad = _all_mvp_candidates()
        if len(broad) > len(candidates):
            broad_result = _ask_gpt(analysis, broad)
            if broad_result.get("recommendations"):
                broad_result["candidates_count"] = len(broad)
                broad_result["widened_search"] = True
                return broad_result

    return result


# ── 독립 실행 테스트 ──
if __name__ == "__main__":
    mock = {
        "case_type": "친족",
        "case_subtype": "양육비",
        "summary": "협의이혼 후 상대방이 매월 50만원 양육비를 6개월째 미지급. "
                   "총 300만원 연체. 상대방은 회사 재직 중인 급여소득자.",
        "extracted_json": {
            "청구인": {"이름": "김영희"}, "상대방": {"이름": "이철수", "직업": "회사원"},
            "월양육비": 500000, "미지급개월": 6,
        },
    }
    out = recommend(mock)
    print(json.dumps(out, ensure_ascii=False, indent=2))


