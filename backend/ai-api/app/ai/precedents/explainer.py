"""후보 판례 중에서 이 상담에 실제로 참고할 것만 골라, 이유를 붙여 돌려준다.

법령 조문과 같은 문제가 판례에도 있다 — 임베딩 유사도는 "같은 분야"까지만
가려내고 "이 사건에 쓸 수 있는가"는 못 가린다. 게다가 판례는 조문보다 나쁘다.
조문은 요건이 글로 적혀 있지만, 판례는 사실관계가 조금만 달라도 결론이
뒤집히는데 본문만 봐서는 그 차이가 잘 안 보인다.

그래서 상담원에게 목록만 내밀면 안 된다. 판례는 "비슷해 보이는데 결론이 반대인
사건"이 가장 위험하고, 그건 순위로는 절대 드러나지 않는다.

구조는 statutes/explainer.py와 같다. 프롬프트와 후보 표기만 판례에 맞춘다 —
공통 부분을 묶는 것도 생각했지만, 조문 쪽은 이미 돌아가는 코드라 시연을 앞두고
건드리지 않는 편을 택했다.
"""
from __future__ import annotations

import json
import logging
import os
from functools import lru_cache
from typing import Any

logger = logging.getLogger(__name__)

# 조문 선별과 같은 모델을 쓴다(statutes/explainer.py MODEL 주석 참고).
MODEL = os.getenv("LLM_MODEL", "gpt-5.4-mini")

# 판례 한 건에서 프롬프트에 넣을 본문 길이. 판시사항·요약이 앞에 오므로
# 앞부분만으로도 무슨 쟁점인지는 판단할 수 있다. 전문까지 다 넣으면 후보
# 30건에서 프롬프트가 수만 자로 불어난다.
_BODY_CLIP = 600
_SUMMARY_CLIP = 700

PROMPT = """너는 법률상담 지원 시스템에서, 검색으로 걸러온 판례 후보 중
이 상담에 실제로 참고할 만한 것만 골라 상담원에게 넘기는 도구다.

## 무엇을 하는가
후보는 뜻이 아니라 글자가 비슷해서 걸려온 것들이라 대부분 관련이 없다.
그중 "이 상담의 사실관계와 쟁점이 실제로 닿는" 판례만 고르고, 판례마다 왜 이
사건에 참고가 되는지를 한 문장으로 쓴다.

## 고르는 기준
1. 쟁점이 같은지로 판단한다. 사건 분야가 같다는 것만으로는 부족하다.

     상담: 남편이 사망했는데 빚이 재산보다 많아 상속을 포기하려 한다
     고름: 상속포기 기간의 기산점을 다룬 판례 — 3개월 기산을 언제로 볼지가 이 상담의 쟁점
     버림: 상속재산분할 비율을 다룬 판례 — 같은 상속이지만 이 사람의 쟁점이 아니다

2. 사실관계가 이 상담과 어긋나는 판례는 뺀다. 결론만 비슷해 보이고 전제가
   다른 판례가 가장 위험하다 — 상담원이 근거로 썼다가 정반대 결과를 맞는다.
3. 상급심을 앞에 둔다. 대법원 판례가 하급심보다 먼저다.
4. 애매하면 뺀다. 적게 주는 편이 낫다.
5. 쓸 만한 것이 하나도 없으면 빈 목록을 낸다. 억지로 채우지 마라.
6. 최대 {limit}건. 그보다 적어도 된다.

## 이유 쓰는 법
1. 반드시 [상담 내용]에 있는 사실만 근거로 든다. 상담에 없는 사실을 지어내
   연결하지 않는다.
2. 판례 내용을 요약하지 마라. 상담원은 판시사항을 옆에서 같이 본다.
   쓸 것은 '이 판례가 무슨 내용인가'가 아니라 '왜 이 사건에 참고가 되는가'다.

     나쁨: "상속포기의 기간에 관한 대법원 판례입니다"        <- 판례 요약
     좋음: "채무 초과 사실을 뒤늦게 안 경우라 기산점이 쟁점이 될 수 있습니다"

3. 한 문장, 60자 이내. 존댓말.
4. 단정하지 마라. 이 판례를 근거로 쓸지는 상담원·변호사가 정한다.
   "~에 해당할 수 있습니다", "~인지 확인이 필요합니다" 같은 표현을 쓴다.

## 출력 JSON
고른 것만, 상담원이 볼 순서대로 낸다. index는 입력에 붙은 번호를 그대로 쓴다.

{{"selected": [{{"index": 12, "reason": "..."}}, {{"index": 3, "reason": "..."}}]}}"""


@lru_cache(maxsize=1)
def _client():
    from openai import OpenAI

    return OpenAI()


def _fallback_reason(item: dict[str, Any], case_label: str) -> str:
    """설명을 못 만들었을 때 쓸 문구."""
    pct = item.get("similarity_percent")
    if pct is None:
        return f"'{case_label}' 상담 내용과 관련"
    return f"'{case_label}' 상담 내용과 {pct}% 유사"


def _fallback(candidates: list[dict[str, Any]], case_label: str,
              limit: int) -> list[dict[str, Any]]:
    """선별이 불가능할 때 유사도 상위 N건으로 돌아간다.

    정확도는 떨어져도 화면은 뜬다. 선별이 안 됐다는 것은 이유 문구가 유사도
    표현인 것과 selected_by로 드러난다."""
    picked = candidates[:limit]
    for item in picked:
        item["reason"] = _fallback_reason(item, case_label)
        item["selected_by"] = "similarity"
    return picked


def _listing_entry(index: int, item: dict[str, Any]) -> str:
    """후보 한 건을 프롬프트에 넣을 모양으로 만든다.

    사건번호·법원·선고일을 제목에 함께 준다 — 어느 심급인지 모르면 3번 기준
    ("상급심을 앞에 둔다")을 지킬 수가 없다."""
    head = " ".join(v for v in (
        item.get("citation") or "",
        item.get("case_number") or "",
    ) if v).strip() or (item.get("title") or "")
    body = (item.get("holding") or item.get("summary")
            or item.get("content") or "")
    return f"[{index}] {head}\n{body[:_BODY_CLIP]}"


def select_and_explain(candidates: list[dict[str, Any]], summary: str,
                       case_label: str, limit: int) -> list[dict[str, Any]]:
    """후보에서 참고할 판례만 골라, 이유를 붙이고 순서대로 돌려준다.

    candidates는 유사도 내림차순으로 들어오고, 반환은 LLM이 정한 순서다.
    후보는 제자리에서 수정한다 — 호출부가 이어서 응답으로 쓰기 때문이다."""
    if not candidates:
        return []

    # 상담 내용이 없으면 판단할 근거가 없다. 유형만으로 고르게 하면 어느
    # 상담이든 같은 답이 나와, 상담별 추천이 아니라 예시 목록이 된다.
    if not (summary or "").strip():
        return _fallback(candidates, case_label, limit)

    listing = "\n\n".join(
        _listing_entry(i, item) for i, item in enumerate(candidates))
    user_msg = (f"[상담 내용]\n{summary[:_SUMMARY_CLIP]}\n\n"
                f"[사건 유형]\n{case_label}\n\n"
                f"[판례 후보 — {len(candidates)}건]\n{listing}")

    try:
        resp = _client().chat.completions.create(
            model=MODEL,
            messages=[{"role": "system", "content": PROMPT.format(limit=limit)},
                      {"role": "user", "content": user_msg}],
            response_format={"type": "json_object"},
            temperature=0,
        )
        parsed = json.loads(resp.choices[0].message.content)
        selected = parsed.get("selected", []) or []
    except Exception as e:
        # 고르지 못해도 판례 목록은 나가야 한다.
        logger.warning("판례 선별 실패: %s: %s", type(e).__name__, e)
        return _fallback(candidates, case_label, limit)

    results: list[dict[str, Any]] = []
    used: set[int] = set()
    for entry in selected:
        if not isinstance(entry, dict):
            continue
        try:
            idx = int(entry.get("index"))
        except (TypeError, ValueError):
            continue
        # 없는 번호를 지어내거나 같은 판례를 두 번 내는 경우를 막는다.
        if not (0 <= idx < len(candidates)) or idx in used:
            continue
        used.add(idx)
        item = candidates[idx]
        reason = str(entry.get("reason", "")).strip()
        item["reason"] = reason or _fallback_reason(item, case_label)
        item["selected_by"] = "llm"
        results.append(item)
        if len(results) >= limit:
            break

    return results
