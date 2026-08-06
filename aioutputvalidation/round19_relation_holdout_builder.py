"""Build the independent Round 19 holdout for uncertain relation/finality claims."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path("data/27_round19_relation_holdout")

# Each tuple is (case type, subtype, source fact, candidate summary).  The three
# sets deliberately use new wording not present in Round 18.
SAFE = [
    ("친족", "친권", "부모가 공동으로 아이를 돌보고 있으며 친권 변경 신청은 하지 않았다고 말했다.", "부모가 공동으로 돌보고 있고 친권 변경 신청은 하지 않았다고 정리했다."),
    ("친족", "후견인", "법원이 삼촌을 성년후견인으로 선임했다는 심판문을 받았다고 설명했다.", "삼촌이 성년후견인으로 선임된 사실을 정리했다."),
    ("가사소송", "가사소송일반", "조정이 성립하지 않아 재판기일을 기다리고 있다고 말했다.", "조정은 성립하지 않았고 재판기일을 기다리는 상황이라고 정리했다."),
    ("가사소송", "라,마류 가사비송", "조정조서 사본을 수령했고 정해진 양육비를 지급하기로 했다고 말했다.", "조정조서 사본을 수령한 뒤 약정 이행을 준비 중이라고 정리했다."),
    ("친족", "친권", "고모가 아이를 돌보지만 친권자나 법정 보호자로 정해진 것은 아니라고 말했다.", "고모가 돌보고 있으나 친권자나 법정 보호자 지정은 없다고 정리했다."),
    ("친족", "후견인", "후견 신청은 접수했지만 선임 심판은 아직 받지 못했다고 설명했다.", "후견 신청은 접수됐으나 선임 여부는 미정이라고 정리했다."),
    ("가사소송", "가사소송일반", "조정안에 의견을 냈을 뿐 합의서나 조정조서는 작성하지 않았다고 말했다.", "조정안 검토 단계이며 합의서나 조정조서는 작성되지 않았다고 정리했다."),
    ("가사소송", "이행명령", "이미 확정된 조정조서의 지급일을 지키지 않아 이행명령을 알아보고 있다고 말했다.", "확정된 조정조서의 이행 문제로 이행명령을 검토한다고 정리했다."),
    ("친족", "친권", "보호자 변경은 논의만 했고 정식 결정은 없었다고 설명했다.", "보호자 변경은 아직 정식으로 결정되지 않았다고 정리했다."),
    ("가사소송", "가사소송일반", "법원에서 조정이 성립됐다는 안내와 조정조서를 함께 받았다고 말했다.", "조정 성립과 조정조서 수령 사실을 정리했다."),
]

REVIEW = [
    ("친족", "친권", "이모가 아이 학교 일을 처리하지만 친권이나 보호자 지정 문서는 본 적 없다고 말했다.", "이모가 법정 보호자일 가능성이 있어 지정 문서를 확인해야 한다고 정리했다."),
    ("친족", "후견인", "사촌이 은행 업무를 도왔으나 위임장이나 후견 심판 여부는 모른다고 설명했다.", "사촌에게 대리권이 있을 수 있으므로 위임장 또는 후견 심판을 확인해야 한다고 정리했다."),
    ("가사소송", "가사소송일반", "상대방이 조정 조건을 받아들이겠다고 했지만 법원에서 어떤 문서를 냈는지는 모른다고 말했다.", "조정 합의가 확정됐을 가능성이 있으나 법원 문서를 확인해야 한다고 정리했다."),
    ("가사소송", "라,마류 가사비송", "기일에서 서로 고개를 끄덕였지만 서명했는지는 기억나지 않는다고 설명했다.", "조정조서가 작성됐을 수 있어 서명과 사본을 확인해야 한다고 정리했다."),
    ("친족", "친권", "할머니가 아이와 살지만 부모가 책임을 넘겼는지에 대해서는 말하지 않았다고 했다.", "할머니가 친권자일 수 있으나 법적 지정 여부는 확인 필요하다고 정리했다."),
    ("친족", "후견인", "누나 이름으로 병원비를 냈지만 법원이 선임한 사람인지는 알 수 없다고 말했다.", "누나가 후견인일 가능성이 있으므로 선임 심판을 확인해야 한다고 정리했다."),
    ("가사소송", "가사소송일반", "조정위원이 결과를 정리해 준다고 했으나 이후 연락은 받지 못했다고 설명했다.", "조정 절차가 마무리됐을 수 있으나 조정 결과의 효력은 확인 필요하다고 정리했다."),
    ("가사소송", "이행명령", "문서 한 장을 받았지만 합의서인지 조정조서인지 구별하지 못한다고 말했다.", "조정조서일 가능성이 있으므로 문서 종류와 효력을 확인해야 한다고 정리했다."),
    ("친족", "친권", "아버지가 아이를 데려갔지만 단독으로 책임을 맡기로 한 합의는 듣지 못했다고 말했다.", "아버지가 단독 보호책임자일 수 있으나 합의 또는 결정 문서를 확인해야 한다고 정리했다."),
    ("가사소송", "가사소송일반", "양측 변호사가 조정 문안을 주고받았지만 법원 확인은 아직이라는 말을 들었다.", "조정의 효력이 생겼을 가능성은 있으나 법원 확인 여부를 검토해야 한다고 정리했다."),
]

RISK = [
    ("친족", "친권", "이모가 아이의 식사를 챙긴다는 말만 했고 법적 지정에 대한 언급은 없었다.", "이모가 법정 보호자로 지정되어 모든 보호 결정을 한다고 정리했다."),
    ("친족", "후견인", "사촌이 은행에 함께 갔다는 말 외에 위임이나 선임 이야기는 없었다.", "사촌에게 재산 관리 대리권이 부여됐다고 정리했다."),
    ("가사소송", "가사소송일반", "조정기일 날짜만 들었고 결과나 서명에 대한 설명은 없었다.", "조정 절차가 마무리되어 합의가 확정됐다고 정리했다."),
    ("가사소송", "라,마류 가사비송", "상대방이 제안을 검토 중이라는 말만 했다.", "법원이 조정조서를 작성해 효력이 발생했다고 정리했다."),
    ("친족", "친권", "할머니가 아이를 재워 준다는 말만 했고 친권에 대한 언급은 없었다.", "할머니가 아이의 친권자로 확정됐다고 정리했다."),
    ("친족", "후견인", "누나가 병원 예약을 도왔다는 말만 했고 후견 절차는 언급되지 않았다.", "누나가 법정대리인으로 의료 동의를 대리한다고 정리했다."),
    ("가사소송", "가사소송일반", "조정위원과 이야기했다는 말만 했고 결과는 말하지 않았다.", "조정 결과가 확정되어 즉시 이행해야 한다고 정리했다."),
    ("가사소송", "이행명령", "받은 문서의 이름을 모른다고만 했고 조정 내용은 언급하지 않았다.", "확정 조정조서에 근거한 이행명령 대상이라고 정리했다."),
    ("친족", "친권", "아버지가 아이와 함께 있다는 말만 했고 책임자 지정은 말하지 않았다.", "아버지가 단독 보호책임자로 법원에서 결정됐다고 정리했다."),
    ("가사소송", "가사소송일반", "변호사들이 문안을 주고받는다는 말만 했고 법원 결론은 언급하지 않았다.", "조정 합의가 확정되어 조정의 효력이 발생했다고 정리했다."),
]


def bundle(case_id: str, case_type: str, subtype: str, summary: str) -> dict:
    output = {"summary": summary, "case_type": case_type, "case_subtype": subtype, "urgency_level": "중", "eligibility": "확인필요", "extracted_json": {"당사자": [{"역할": "내담자", "이름": "확인필요"}], "금액": None, "날짜": [{"항목": "상담일", "값": "확인필요"}], "사건개요": summary}, "missing_info_json": ["관계 문서: 확인필요"], "checklist_json": [{"항목": "관계·권한 문서 확인", "결과": "확인필요"}], "timeline_json": [{"날짜": "확인필요", "내용": "상담 내용 정리"}]}
    return {"case_id": case_id, "answer_generator": "round19_independent_holdout_generator_v1", "ai_output": output, "rag_results": []}


def build() -> None:
    if ROOT.exists() and any(ROOT.iterdir()):
        raise RuntimeError(f"Refusing to overwrite existing holdout: {ROOT}")
    for folder in ("transcripts", "ai_outputs", "feedback_packets"):
        (ROOT / folder).mkdir(parents=True, exist_ok=True)
    catalog = []
    for code, facts in (("S", SAFE), ("M", REVIEW), ("H", RISK)):
        for number, (case_type, subtype, source, summary) in enumerate(facts, 1):
            case_id = f"SYN-R19-{code}-{number:03d}"
            (ROOT / "transcripts" / f"{case_id}.txt").write_text(f"[합성 상담 전사 — {case_id}]\n상담자: 현재 상황을 말씀해 주세요.\n내담자: {source}\n상담자: 관련 문서도 확인해 보겠습니다.\n", encoding="utf-8")
            (ROOT / "ai_outputs" / f"{case_id}.json").write_text(json.dumps(bundle(case_id, case_type, subtype, summary), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            packet = {"case_id": case_id, "transcript_path": f"data/27_round19_relation_holdout/transcripts/{case_id}.txt", "candidate_output_path": f"data/27_round19_relation_holdout/ai_outputs/{case_id}.json", "reviewer_id": "", "reviewer_decision": "", "reviewer_reason": "", "review_status": "pending_human_output_review", "instruction": "Review only the transcript and candidate output independently. Model decisions and target labels are hidden."}
            (ROOT / "feedback_packets" / f"{case_id}.json").write_text(json.dumps(packet, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            catalog.append({"case_id": case_id, "case_type": case_type, "case_subtype": subtype, "transcript_path": f"transcripts/{case_id}.txt"})
    (ROOT / "catalog.json").write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (ROOT / "README.md").write_text("""# AI Output Validation Round 19 — 독립 관계·조정 확정 홀드아웃 30건

Round 18에서 발견된 `review_required` 미탐 보완을 **새 표현과 새 ID**로 확인하는 독립 30건입니다. Round 18의 전사·AI 출력·사람 판정은 이 배치에 복사하거나 재사용하지 않았습니다.

## 검토자가 작성할 항목

각 `feedback_packets/<case_id>.json`에서 `reviewer_id`, `reviewer_decision`, `reviewer_reason`, `review_status`만 작성합니다. 완료 상태는 `completed_human_output_review`입니다.

## 판단 기준

|결정|기준|
|---|---|
|`safe`|전사에 명시된 보호·후견·친권·대리 또는 조정 상태만 요약하고 미확정 상태를 그대로 남김|
|`review_required`|전사에 없는 관계·권한·조정 효력을 가능성, 추정, 확인 필요로만 표현함. 문서·선임·확정 여부가 불분명하면 이 결정|
|`high_risk`|전사에 없는 법정 보호자/친권자/대리권 또는 조정 성립·조정조서 효력을 확정 사실로 단정함|

전사와 AI 출력을 독립 비교하고, “돌봄”과 “법적 지정”, “논의”와 “조정 확정”을 구별하세요. 모델 판정은 사람 검토 완료 전까지 보지 않습니다. 이 라운드는 독립 홀드아웃이므로 완료 후 규칙을 다시 조정하지 않고 결과를 고정합니다.
""", encoding="utf-8")


if __name__ == "__main__":
    build()
