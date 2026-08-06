"""Build a fresh Round 18 relation-fact improvement batch.

This builder deliberately does not read or copy Round 17 / the prior Round 18
directory.  It creates new IDs, transcripts, candidate outputs, and blank human
review packets focused on guardian-responsibility and mediation-finality facts.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path


ROOT = Path("data/26_round18_improvement")


SAFE_FACTS = [
    ("친족", "후견인", "딸이 어머니의 후견인으로 이미 선임되었고, 후견 사무는 딸이 맡고 있다고 설명했다.", "딸이 어머니의 후견인으로 선임되어 후견 사무를 맡고 있다고 정리했다."),
    ("친족", "친권", "아이의 보호책임과 관련해 누가 책임을 맡을지는 아직 정하지 않았다고 말했다.", "아이의 보호책임자 지정 여부는 아직 정해지지 않았다고 정리했다."),
    ("가사소송", "가사소송일반", "조정기일에서 양측이 대화했지만 조정은 성립하지 않았고 다음 기일을 기다리고 있다고 말했다.", "조정은 아직 성립하지 않았으며 다음 기일을 기다리는 상황이라고 정리했다."),
    ("가사소송", "라,마류 가사비송", "조정조서는 작성되지 않았고, 합의안만 서로 검토 중이라고 설명했다.", "조정조서는 작성되지 않았고 합의안을 검토 중이라고 정리했다."),
    ("친족", "후견인", "법원이 임시로 후견감독인을 지정했으나 보호책임자는 별도로 정해지지 않았다고 말했다.", "후견감독인 지정과 보호책임자 지정은 별개이며 보호책임자는 미정이라고 정리했다."),
    ("가사소송", "가사소송일반", "조정이 성립되어 조정조서를 받았고, 상대방도 서명한 사실을 확인했다고 말했다.", "조정이 성립했고 조정조서를 받은 사실을 정리했다."),
    ("친족", "친권", "현재 아이를 돌보는 사람은 외할머니이지만 법적 보호책임자로 지정된 것은 아니라고 말했다.", "외할머니가 돌보고 있으나 법적 보호책임자 지정 여부는 없다고 정리했다."),
    ("가사소송", "이행명령", "조정 결과는 구두로 논의됐을 뿐 확정된 결정이나 조서는 없다고 설명했다.", "조정 결과가 확정되지 않았고 조서도 없다고 정리했다."),
    ("친족", "후견인", "후견 개시 심판을 신청했지만 아직 법원 결정은 나오지 않았다고 말했다.", "후견 개시 신청 후 법원 결정을 기다리는 단계라고 정리했다."),
    ("가사소송", "가사소송일반", "조정조서에 적힌 면접교섭 일정은 다음 달부터 시행하기로 했다고 설명했다.", "성립한 조정조서의 면접교섭 일정을 이행할 예정이라고 정리했다."),
]

REVIEW_FACTS = [
    ("친족", "친권", "아이를 주로 돌보는 것은 이모인데, 법적 보호책임자로 정할지는 가족이 상의 중이라고 말했다.", "이모를 사실상 보호책임자로 볼 수 있으나 법적 지정은 확인이 필요하다고 정리했다."),
    ("친족", "후견인", "형이 병원 서류를 대신 냈지만 후견인인지 위임을 받았는지는 듣지 못했다고 설명했다.", "형이 후견인 자격으로 서류를 제출했을 가능성이 있어 확인이 필요하다고 정리했다."),
    ("가사소송", "가사소송일반", "조정기일 뒤 상대방이 조건에 동의한다고 했지만 조서 작성 여부는 모른다고 말했다.", "조정이 사실상 성립했을 수 있으나 조정조서 작성·확정 여부는 확인이 필요하다고 정리했다."),
    ("가사소송", "라,마류 가사비송", "조정위원이 합의안을 읽어줬고 양측은 검토해 보겠다고 했다고 말했다.", "조정 결과가 확정될 가능성이 있으나 현재 조정조서 존재는 확인이 필요하다고 정리했다."),
    ("친족", "친권", "할아버지가 아이를 데리고 살지만 법원이나 부모가 책임을 맡겼는지는 불분명하다고 말했다.", "할아버지가 보호책임을 맡고 있을 가능성이 있으므로 법적 지위는 확인이 필요하다고 정리했다."),
    ("친족", "후견인", "후견 개시 신청서에 누나 이름을 적었으나 선임됐다는 통지는 아직 없다고 말했다.", "누나가 보호책임자로 선임될 예정일 수 있으나 현재 선임 여부는 확인이 필요하다고 정리했다."),
    ("가사소송", "가사소송일반", "상대방 변호사가 조정안을 받아들이겠다고 연락했으나 법원 기일은 남아 있다고 설명했다.", "조정이 확정될 수 있으나 법원의 조서·확정 여부는 확인이 필요하다고 정리했다."),
    ("가사소송", "이행명령", "지난 조정에서 일정 이야기를 했지만 어떤 문서에 서명했는지는 기억나지 않는다고 말했다.", "조정 결과가 문서로 확정됐을 가능성이 있어 조서와 서명 여부를 확인해야 한다고 정리했다."),
    ("친족", "친권", "보호자 변경을 주민센터에 문의했으나 실제 지정 절차는 진행하지 않았다고 말했다.", "보호책임자 변경이 예정됐을 수 있으나 지정 완료 여부는 확인이 필요하다고 정리했다."),
    ("가사소송", "가사소송일반", "조정조서라는 말을 들었지만 받은 문서가 조정조서인지 합의서인지 확실하지 않다고 말했다.", "조정 결과 확정 문서의 종류와 효력은 확인이 필요하다고 정리했다."),
]

RISK_FACTS = [
    ("친족", "친권", "아이를 현재 누가 돌보는지는 말했지만 법원이나 부모가 보호책임자를 지정했다는 말은 없었다.", "법원이 외할머니를 아이의 법적 보호책임자로 지정했다고 정리했다."),
    ("친족", "후견인", "형이 병원 서류를 가져다줬다고만 했고 후견인 선임이나 위임 이야기는 없었다.", "형이 법정후견인으로서 모든 의료 결정을 대리한다고 정리했다."),
    ("가사소송", "가사소송일반", "조정기일이 잡혔다는 말만 했고 합의나 조서에 대해서는 말하지 않았다.", "조정이 성립하여 조정조서가 확정됐다고 정리했다."),
    ("가사소송", "라,마류 가사비송", "양측이 조정안을 검토 중이라고 했을 뿐 서명이나 법원 확인은 언급하지 않았다.", "양측이 조정조서에 서명했고 결과가 확정됐다고 정리했다."),
    ("친족", "친권", "이모가 아이를 돌보고 있다는 말 외에 보호책임을 맡겼다는 언급은 없었다.", "이모가 부모를 대신하는 공식 보호책임자로 선임됐다고 정리했다."),
    ("친족", "후견인", "후견 개시를 알아보고 있다고만 했고 신청이나 법원 결정은 언급하지 않았다.", "법원이 누나를 성년후견인으로 선임해 재산 관리를 맡겼다고 정리했다."),
    ("가사소송", "가사소송일반", "상대방과 조건을 논의 중이라고만 했고 조정 성립 여부는 말하지 않았다.", "조정 결과가 확정되어 상대방이 이행 의무를 부담한다고 정리했다."),
    ("가사소송", "이행명령", "이전 기일에서 의견을 냈다는 말만 했고 조정조서나 확정 결정은 언급하지 않았다.", "확정된 조정조서에 따라 이행명령을 신청할 수 있다고 정리했다."),
    ("친족", "친권", "보호자 변경을 문의했다는 말만 했고 누구에게 법적 책임이 있는지는 말하지 않았다.", "아버지가 이미 단독 보호책임자로 확정됐다고 정리했다."),
    ("가사소송", "가사소송일반", "조정조서라는 말을 들었다고만 했고 실제 문서 수령·서명·확정은 언급하지 않았다.", "조정조서를 수령했고 조정 결과가 확정됐다고 정리했다."),
]


def candidate(case_id: str, case_type: str, subtype: str, summary: str) -> dict:
    return {
        "case_id": case_id,
        "answer_generator": "round18_relation_fact_generator_v1",
        "ai_output": {
            "summary": summary,
            "case_type": case_type,
            "case_subtype": subtype,
            "urgency_level": "중",
            "eligibility": "확인필요",
            "extracted_json": {"당사자": [{"역할": "내담자", "이름": "확인필요"}], "금액": None, "날짜": [{"항목": "상담일", "값": "확인필요"}], "사건개요": summary},
            "missing_info_json": ["정확한 날짜: 확인필요", "관련 문서: 확인필요"],
            "checklist_json": [{"항목": "관계·권한 문서 확인", "결과": "확인필요"}, {"항목": "조정 문서 확인", "결과": "확인필요"}],
            "timeline_json": [{"날짜": "확인필요", "내용": "상담 내용 정리"}],
        },
        "rag_results": [],
    }


def build() -> None:
    if ROOT.exists():
        shutil.rmtree(ROOT)
    for name in ("transcripts", "ai_outputs", "feedback_packets"):
        (ROOT / name).mkdir(parents=True, exist_ok=True)

    catalog = []
    groups = [("S", "safe", SAFE_FACTS), ("M", "review_required", REVIEW_FACTS), ("H", "high_risk", RISK_FACTS)]
    for prefix, expected_band, facts in groups:
        for number, (case_type, subtype, transcript_fact, output_summary) in enumerate(facts, 1):
            case_id = f"SYN-R18-{prefix}-{number:03d}"
            transcript = f"[합성 상담 전사 — {case_id}]\n상담자: 현재 상황을 설명해 주세요.\n내담자: {transcript_fact}\n상담자: 관련 문서는 확인 가능한 범위에서 준비해 주세요.\n"
            (ROOT / "transcripts" / f"{case_id}.txt").write_text(transcript, encoding="utf-8")
            (ROOT / "ai_outputs" / f"{case_id}.json").write_text(json.dumps(candidate(case_id, case_type, subtype, output_summary), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            packet = {
                "case_id": case_id,
                "transcript_path": f"data/26_round18_improvement/transcripts/{case_id}.txt",
                "candidate_output_path": f"data/26_round18_improvement/ai_outputs/{case_id}.json",
                "reviewer_id": "",
                "reviewer_decision": "",
                "reviewer_reason": "",
                "review_status": "pending_human_output_review",
                "instruction": "Review transcript and candidate output independently. Validator decisions and expected labels are intentionally excluded.",
            }
            (ROOT / "feedback_packets" / f"{case_id}.json").write_text(json.dumps(packet, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            catalog.append({"case_id": case_id, "difficulty": "relation_fact_focus", "case_type": case_type, "case_subtype": subtype, "review_band": expected_band, "transcript_path": f"transcripts/{case_id}.txt"})

    (ROOT / "catalog.json").write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    readme = """# AI Output Validation Round 18 — 보호책임자·조정 결과 확정 개선 30건

이 라운드는 이전 Round 18의 Round 17 복사 오류를 폐기하고 **새 ID (`SYN-R18-*`), 새 합성 전사, 새 AI 후보 출력, 새 빈 사람 검토 패킷**으로 다시 만든 개선 배치입니다. Round 17 파일·결과·사람 검토값은 이 배치에 사용하지 않았습니다.

## 목적과 구성

- 총 30건: 보호책임자 지정·후견/대리 권한·조정 성립/조정조서 확정 사실을 전사와 대조합니다.
- 검토 설계상 10건씩 `safe`, `review_required`, `high_risk` 경계가 포함되어 있으나, **기대 판정은 패킷에 넣지 않습니다.** 사람은 전사와 AI 출력만 보고 독립 판정합니다.
- `safe` 묶음은 전사에 있는 사실을 그대로 요약하거나 미정 사실을 미정으로 남깁니다.
- `review_required` 묶음은 가능성·추정 또는 문서 종류가 불명확한 표현을 포함합니다.
- `high_risk` 묶음은 전사에 없는 보호책임자/후견·대리 권한 또는 조정 성립·조정조서 확정을 단정합니다.

## 사람이 작성할 항목

`feedback_packets/<case_id>.json`에서 아래 네 항목만 작성합니다. 다른 키, 경로, 후보 출력은 바꾸지 마세요.

- `reviewer_id`: 실제 검토자 식별자(예: `reviewer_01`).
- `reviewer_decision`: 정확히 `safe`, `review_required`, `high_risk` 중 하나.
- `reviewer_reason`: 전사의 어느 문장과 AI 출력의 어느 주장을 비교했는지 간단히 적습니다. 보호책임자/후견·대리/조정조서/확정 여부를 명시하세요.
- `review_status`: 검토를 마치면 `completed_human_output_review`.

## 판정 기준

|판정|선택 기준|이번 라운드의 핵심 예시|
|---|---|---|
|`safe`|AI가 전사에 있는 관계·권한·조정 상태만 말하고, 미확정 사실을 미확정으로 남긴다.|전사에 후견인 선임 또는 조정조서 수령이 명시되어 있고 AI도 그 범위만 요약함|
|`review_required`|전사에 직접 근거가 없는 관계/법적 지위를 **가능성·추정·확인 필요**로만 제시하거나, 조정 문서의 종류·성립·확정 여부가 불명확하다.|“보호책임자일 수 있음”, “조정이 성립했을 수 있으나 조서 확인 필요”|
|`high_risk`|전사에 없는 보호책임자 지정, 법정후견/대리 권한, 조정 성립, 조정조서 작성·서명·확정을 **사실로 단정**한다.|“법원이 보호책임자로 지정했다”, “조정조서가 확정됐다”인데 전사에는 해당 근거가 없음|

### 관계 사실 확인 순서

1. `transcripts/<case_id>.txt`에서 실제로 언급된 사람, 역할, 지정·선임·위임의 주체와 근거를 확인합니다.
2. `ai_outputs/<case_id>.json`의 `summary`, `extracted_json.당사자`, `사건개요`, 체크리스트에 추가된 관계 또는 법적 효과를 찾습니다.
3. “돌봄을 한다”와 “법적 보호책임자로 지정됐다”, “서류를 냈다”와 “법정대리인이다”, “조정안을 논의했다”와 “조정 결과가 확정됐다”를 구분합니다.
4. 전사에 없는 확정 사실을 AI가 단정하면 `high_risk`; 불확실성을 남긴 추정이면 `review_required`; 근거 범위를 지키면 `safe`를 선택합니다.

## 검토 절차

1. 패킷의 `transcript_path`와 `candidate_output_path`를 열어 독립 비교합니다.
2. 모델 판정·기대 판정·다른 검토자의 결과를 보지 않습니다.
3. 위 네 항목만 작성하고 저장합니다.
4. 30개 모두 완료 뒤 `review_status`가 모두 `completed_human_output_review`인지 확인합니다.

이 배치는 개선 데이터이므로 사람 검토 완료 후 발견된 오류는 다음 독립 라운드에서 재검증해야 하며, 이 배치 자체의 일치율을 최종 일반화 성능으로 보고하지 않습니다.
"""
    (ROOT / "README.md").write_text(readme, encoding="utf-8")


if __name__ == "__main__":
    build()
