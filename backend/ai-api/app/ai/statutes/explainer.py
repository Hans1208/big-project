"""후보 조문 중에서 이 상담에 실제로 쓸 것만 골라, 이유를 붙여 돌려준다.

임베딩은 2,258개에서 후보를 좁히는 일은 잘하지만, 그중 어느 게 맞는지는
못 고른다. 실측에서 전체 점수가 90.6%~78.7%의 12%p 폭에 몰려 있고, 아무
상관 없는 민사소송법 조문도 78.7%를 받는다. 10위와 100위 차이가 2.2%p라
상위권에서는 사실상 순서가 없는 것과 같다.

그래서 역할을 나눈다. 임베딩은 예선(후보 여러 건), 판단은 여기서 한다.
'두 글뭉치가 닮았나'가 아니라 '이 사람 상황에 이 제도를 쓸 수 있나'를 묻는
일이라 거리 계산으로는 안 되고, 조문을 읽고 요건을 따져야 한다.

실제로 양육비 미지급 상담에서 정답인 가사소송법 제63조의2가 9위에 있었고
그 위를 가족관계증명서 관련 조문들이 차지했다 — 요약문 끝에 붙은
"추가자료(가족관계증명서/주민등록등본) 확인 완료"라는 사무 메모 때문이다.
사람은 그 문장이 사건 내용이 아님을 알아보지만 임베딩은 평균에 섞는다.

조문마다 부르지 않고 한 번에 묶어 묻는다. 추천은 상담을 바꿀 때마다 도는데,
건마다 부르면 호출도 그만큼 늘어 화면이 눈에 띄게 느려진다.

고르지 못했을 때 추천 자체를 막지는 않는다. 순서가 아쉬울 뿐이지만,
목록까지 못 주면 화면이 통째로 빈다.
"""
from __future__ import annotations

import json
import logging
import os
from functools import lru_cache
from typing import Any

logger = logging.getLogger(__name__)

MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")

# 후보 하나당 넣을 조문 본문 길이. 조문 평균 본문이 175자라 30건을 다 넣어도
# 보통 6천 자 안쪽이고, 항이 많은 긴 조문만 여기서 잘린다. 어느 조문인지
# 알아보고 요건을 따지는 데는 앞부분으로 충분하다.
_ARTICLE_CLIP = 500
_SUMMARY_CLIP = 700

PROMPT = """너는 법률상담 지원 시스템에서, 검색으로 걸러온 법령 조문 후보 중
이 상담에 실제로 쓸 수 있는 것만 골라 상담원에게 넘기는 도구다.

## 무엇을 하는가
후보는 뜻이 아니라 글자가 비슷해서 걸려온 것들이라 대부분 관련이 없다.
그중 "이 상담의 사실관계에 실제로 적용되는" 조문만 고르고, 조문마다 왜 이
사건에 관련되는지를 한 문장으로 쓴다.

## 고르는 기준
1. 이 사람이 처한 상황에 그 제도를 쓸 수 있는지로 판단한다. 사건과 같은
   분야라는 것만으로는 부족하다.

     상담: 양육비를 6개월째 못 받고 있다
     고름: 양육비 직접지급명령 — 2회 이상 미지급이면 상대방 급여에서 뗀다
     버림: 가족관계증명서의 종류 — 같은 가사 분야지만 이 사람이 쓸 제도가 아니다

2. 상담원이 먼저 봐야 할 것부터 순서대로 낸다. 실제로 쓸 수단이 앞이고,
   배경으로 알아둘 조문이 뒤다.
3. 애매하면 뺀다. 관련 없는 조문이 섞이면 상담원이 그걸 검토하느라 시간을
   쓰고, 근거로 잘못 쓸 수도 있다. 적게 주는 편이 낫다.
4. 쓸 만한 것이 하나도 없으면 빈 목록을 낸다. 억지로 채우지 마라.
5. 최대 {limit}건. 그보다 적어도 된다.

## 이유 쓰는 법
1. 반드시 [상담 내용]에 있는 사실만 근거로 든다. 상담에 없는 사실을 지어내
   연결하지 않는다.
2. 조문 내용을 요약하지 마라. 상담원은 조문 본문을 옆에서 같이 본다.
   쓸 것은 '조문이 무슨 내용인가'가 아니라 '왜 이 사건에 관련되는가'다.

     나쁨: "양육비 직접지급명령에 관한 조문입니다"     <- 조문 요약
     좋음: "6개월째 미지급이라 상대방 급여에서 직접 받을 수 있는지 확인이 필요합니다"

3. 한 문장, 60자 이내. 존댓말.
4. 단정하지 마라. 이 조문을 근거로 쓸지는 상담원·변호사가 정한다.
   "~에 해당할 수 있습니다", "~인지 확인이 필요합니다" 같은 표현을 쓴다.

## 출력 JSON
고른 것만, 상담원이 볼 순서대로 낸다. index는 입력에 붙은 번호를 그대로 쓴다.

{{"selected": [{{"index": 12, "reason": "..."}}, {{"index": 3, "reason": "..."}}]}}"""


@lru_cache(maxsize=1)
def _client():
    from openai import OpenAI

    return OpenAI()


def _fallback_reason(item: dict[str, Any], case_label: str) -> str:
    """설명을 못 만들었을 때 쓸 문구.

    유사도를 그대로 문장으로 옮긴다. 이유라기엔 약하지만, 최소한 순위가
    무엇으로 매겨졌는지는 알려준다."""
    pct = item.get("similarity_percent")
    if pct is None:
        return f"'{case_label}' 상담 내용과 관련"
    return f"'{case_label}' 상담 내용과 {pct}% 유사"


def _fallback(candidates: list[dict[str, Any]], case_label: str,
              limit: int) -> list[dict[str, Any]]:
    """선별이 불가능할 때 예전 동작(유사도 상위 N건)으로 돌아간다.

    정확도는 떨어져도 화면은 뜬다. 선별이 안 됐다는 것은 이유 문구가 유사도
    표현인 것과 selected_by로 드러난다."""
    picked = candidates[:limit]
    for item in picked:
        item["reason"] = _fallback_reason(item, case_label)
        item["selected_by"] = "similarity"
    return picked


def select_and_explain(candidates: list[dict[str, Any]], summary: str,
                       case_label: str, limit: int) -> list[dict[str, Any]]:
    """후보에서 쓸 조문만 골라, 이유를 붙이고 순서대로 돌려준다.

    candidates는 유사도 내림차순으로 들어오고, 반환은 LLM이 정한 순서다.
    후보는 제자리에서 수정한다 — 호출부가 이어서 응답으로 쓰기 때문에 새
    리스트를 만들면 두 벌을 관리해야 한다."""
    if not candidates:
        return []

    # 상담 내용이 없으면 판단할 근거가 없다. 유형만으로 고르게 하면 어느
    # 상담이든 같은 답이 나와, 상담별 추천이 아니라 예시 목록이 된다.
    if not (summary or "").strip():
        return _fallback(candidates, case_label, limit)

    listing = "\n\n".join(
        f"[{i}] {item.get('title', '')}\n{(item.get('content') or '')[:_ARTICLE_CLIP]}"
        for i, item in enumerate(candidates)
    )
    user_msg = (f"[상담 내용]\n{summary[:_SUMMARY_CLIP]}\n\n"
                f"[사건 유형]\n{case_label}\n\n"
                f"[조문 후보 — {len(candidates)}건]\n{listing}")

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
        # 고르지 못해도 조문 목록은 나가야 한다.
        logger.warning("조문 선별 실패: %s: %s", type(e).__name__, e)
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
        # 없는 번호를 지어내거나 같은 조문을 두 번 내는 경우를 막는다.
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

    logger.info("조문 선별: 후보 %d건 -> %d건", len(candidates), len(results))
    # 한 건도 못 골랐을 때 유사도 상위로 채우지 않는다. 그렇게 채운 5건이
    # 바로 지금 고치려는 문제다 — 관련 없는 조문을 추천이라며 내미는 것.
    return results
