"""추천된 조문이 '왜' 이 상담에 맞는지 한 줄로 설명한다.

유사도만 돌려주면 추천이 아니라 순위표다. 상담원은 "이 조문이 왜 여기 있는지"를
알아야 검토에 쓸 수 있고, 틀린 추천도 이유를 보고 걸러낼 수 있다. 실제로
유사도는 맞고 틀림을 못 가른다 — 실측에서 맞은 추천이 87.2%, 틀린 추천이
88.6%로 오히려 틀린 쪽이 높았다.

조문 하나마다 부르지 않고 한 번에 묶어 묻는다. 추천은 상담을 바꿀 때마다
자동으로 도는데, 5건이면 호출도 5배가 되어 화면이 눈에 띄게 느려진다.

설명이 실패하면 추천 자체를 막지 않는다. 이유가 없는 추천은 아쉬울 뿐이지만,
이유를 못 만들었다고 조문 목록까지 못 주면 화면이 통째로 빈다.
"""
from __future__ import annotations

import json
import logging
import os
from functools import lru_cache
from typing import Any

logger = logging.getLogger(__name__)

MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")

# 설명에 넣을 조문 본문 길이. 항이 많은 조문은 2천 자가 넘는데, 다 넣으면
# 5건만 묶어도 프롬프트가 1만 자를 넘어 느려진다. 어느 조문인지 알아보고
# 상담과 연결 짓는 데는 앞부분으로 충분하다.
_ARTICLE_CLIP = 700
_SUMMARY_CLIP = 700

PROMPT = """너는 법률상담 지원 시스템에서, 검색된 법령 조문이 이 상담과 어떤 관련이
있는지 상담원에게 한 줄로 설명하는 도구다.

## 무엇을 쓰는가
조문마다 "이 상담의 어떤 사실 때문에 이 조문이 관련되는지"를 한 문장으로 쓴다.
상담원이 그 한 줄만 읽고 이 조문을 열어볼지 말지 정할 수 있어야 한다.

## 규칙
1. 반드시 [상담 내용]에 있는 사실만 근거로 든다. 상담에 없는 사실을 지어내
   연결하지 않는다.
2. 조문 내용을 요약하지 마라. 상담원은 조문 본문을 옆에서 같이 본다.
   쓸 것은 '조문이 무슨 내용인가'가 아니라 '왜 이 사건에 관련되는가'다.

     나쁨: "재산분할청구권에 관한 조문입니다"        ← 조문 요약
     좋음: "협의이혼 후 2년이 지나기 전이라 청구할 수 있는지 확인이 필요합니다"

3. 상담 내용과 이 조문을 이을 근거가 없으면 관련 없다고 솔직히 쓴다.
   억지로 이어붙이면 상담원이 엉뚱한 조문을 검토하게 된다. 검색은 뜻이 아니라
   글자가 비슷해도 걸리므로, 관련 없는 조문이 섞이는 것은 정상이다.
   그 경우 relevant를 false로 두고 왜 관련이 없는지 짧게 쓴다.
4. 한 문장, 60자 이내. 존댓말.
5. 단정하지 마라. 이 조문을 근거로 쓸지는 상담원·변호사가 정한다.
   "~에 해당할 수 있습니다", "~인지 확인이 필요합니다" 같은 표현을 쓴다.

## 출력 JSON
조문마다 하나씩, 입력에 붙은 번호를 그대로 달아서 낸다. 관련 없는 조문도
빠뜨리지 말고 낸다 — 관련이 없다는 것도 상담원에게 필요한 정보다.
설명이 비슷해진다고 묶거나 생략하지 마라.

{"reasons": [{"index": 0, "relevant": true, "reason": "..."},
             {"index": 1, "relevant": false, "reason": "..."}]}"""


@lru_cache(maxsize=1)
def _client():
    from openai import OpenAI

    return OpenAI()


def _fallback(item: dict[str, Any], case_label: str) -> str:
    """설명을 못 만들었을 때 쓸 문구.

    유사도를 그대로 문장으로 옮긴다. 이유라기엔 약하지만, 최소한 순위가
    무엇으로 매겨졌는지는 알려준다."""
    pct = item.get("similarity_percent")
    if pct is None:
        return f"'{case_label}' 상담 내용과 관련"
    return f"'{case_label}' 상담 내용과 {pct}% 유사"


def explain(results: list[dict[str, Any]], summary: str, case_label: str) -> list[dict[str, Any]]:
    """추천 결과에 reason(과 relevant)을 붙여 돌려준다.

    results는 제자리에서 수정하고 그대로 반환한다 — 호출부가 이어서 응답으로
    쓰기 때문에 새 리스트를 만들면 두 벌을 관리해야 한다."""
    if not results:
        return results

    if not (summary or "").strip():
        for item in results:
            item["reason"] = _fallback(item, case_label)
            item["relevant"] = None
        return results

    listing = "\n\n".join(
        f"[{i}] {item.get('title', '')}\n{(item.get('content') or '')[:_ARTICLE_CLIP]}"
        for i, item in enumerate(results)
    )
    user_msg = (f"[상담 내용]\n{summary[:_SUMMARY_CLIP]}\n\n"
                f"[사건 유형]\n{case_label}\n\n"
                f"[검색된 조문 — {len(results)}개, 번호를 그대로 달아서 {len(results)}개를 "
                f"모두 답하세요]\n{listing}")

    reasons: list[dict[str, Any]] = []
    try:
        resp = _client().chat.completions.create(
            model=MODEL,
            messages=[{"role": "system", "content": PROMPT},
                      {"role": "user", "content": user_msg}],
            response_format={"type": "json_object"},
            temperature=0,
        )
        parsed = json.loads(resp.choices[0].message.content)
        reasons = parsed.get("reasons", []) or []
    except Exception as e:
        # 설명이 없어도 조문 목록은 그대로 나가야 한다.
        logger.warning("추천 이유 생성 실패: %s: %s", type(e).__name__, e)

    # 번호로 짝짓는다. 순서에만 기대면 설명이 하나라도 빠졌을 때 전부 한 칸씩
    # 밀려, 엉뚱한 조문에 그럴듯한 이유가 붙는다 — 없는 것보다 나쁘다.
    # 실제로 4개 조문에 설명 1개만 온 적이 있다(관련 없는 조문을 묶어버린 것으로
    # 보인다). 번호가 있으면 그 1개는 제자리에 쓰고 나머지만 폴백으로 채운다.
    by_index: dict[int, dict] = {}
    for r in reasons:
        if not isinstance(r, dict):
            continue
        try:
            idx = int(r.get("index"))
        except (TypeError, ValueError):
            continue
        if 0 <= idx < len(results):
            by_index[idx] = r

    if len(by_index) < len(results):
        logger.warning("추천 이유 %d개 조문 중 %d개만 생성됨",
                       len(results), len(by_index))

    for i, item in enumerate(results):
        r = by_index.get(i)
        text = str((r or {}).get("reason", "")).strip()
        item["reason"] = text or _fallback(item, case_label)
        item["relevant"] = bool(r.get("relevant", True)) if r else None
    return results
