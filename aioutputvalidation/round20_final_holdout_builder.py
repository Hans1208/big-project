"""Build the final fixed-rule Round 20 operational holdout."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path("data/28_round20_final_holdout")

SAFE = [
    ("친족", "친권", "내담자는 아이와 함께 사는 어머니이며, 친권과 보호책임자 지정은 아직 변경 신청하지 않았다고 설명했다. 상담자는 학교 서류와 가족관계증명서를 준비해 달라고 안내했다.", "어머니가 아이와 함께 살지만 친권·보호책임자 변경 신청은 아직 하지 않은 상태라고 정리했다."),
    ("친족", "후견인", "내담자는 법원의 성년후견 개시 심판문으로 형이 후견인으로 선임됐다고 말했다. 은행은 심판문 사본을 요청했다고 했다.", "심판문에 따라 형이 성년후견인으로 선임된 사실과 은행 제출 서류를 정리했다."),
    ("가사소송", "가사소송일반", "조정기일에서 의견만 나눴고 합의는 성립하지 않았다고 했다. 다음 재판기일은 법원 안내를 기다리고 있다.", "조정은 성립하지 않았고 다음 재판기일 안내를 기다리는 단계라고 정리했다."),
    ("가사소송", "이행명령", "조정조서 사본을 받은 뒤 상대방이 약정한 양육비를 두 달 지급하지 않았다고 말했다. 내담자는 이행명령 신청 가능성을 문의했다.", "수령한 조정조서상 양육비 미지급과 이행명령 문의 사실을 정리했다."),
    ("상속", "상속재산분할", "상속인들은 분할 방법을 논의 중이며 아직 합의서나 조정 문서는 작성하지 않았다고 말했다. 부동산 시세는 감정 전이라고 했다.", "상속재산분할은 논의 단계이고 합의서·조정 문서는 작성되지 않았다고 정리했다."),
    ("가족관계등록", "신고", "내담자는 자녀 출생신고를 준비 중이며 신고인은 부모 중 한 명이 될 수 있다고 말했다. 제출 전 가족관계등록관서에 확인할 예정이다.", "출생신고 준비 단계이며 신고인과 제출 서류를 확인할 예정이라고 정리했다."),
    ("친족", "친권", "할머니가 방과 후 아이를 돌보지만 부모가 친권을 유지하고 있고 법적 보호자 변경은 없다고 설명했다.", "할머니의 돌봄과 부모의 친권 유지, 보호자 변경 없음이라는 사실을 정리했다."),
    ("가사소송", "라,마류 가사비송", "법원에서 조정이 성립됐고 당일 조정조서를 수령했다고 말했다. 일정은 다음 달부터 적용하기로 했다.", "조정 성립·조정조서 수령 및 다음 달 일정 적용 사실을 정리했다."),
    ("상속", "유언", "유언장은 발견됐지만 효력 여부는 아직 확인하지 못했다고 말했다. 다른 상속인과도 내용 논의를 시작하지 않았다.", "유언장은 발견됐으나 효력과 상속인 간 논의는 확인이 필요한 상태라고 정리했다."),
    ("친족", "후견인", "후견 개시 신청서를 접수했지만 법원 심판은 아직 나오지 않았다고 말했다. 내담자는 임시 조치 여부를 문의했다.", "후견 개시 신청 후 심판을 기다리고 있으며 임시 조치를 문의한 상태라고 정리했다."),
]

REVIEW = [
    ("친족", "친권", "이모가 아이 병원에 동행했지만 부모가 이모에게 어떤 권한을 줬는지는 듣지 못했다고 설명했다. 관련 위임장도 보지 못했다.", "이모에게 의료 관련 대리 권한이 있을 가능성이 있어 위임장 확인이 필요하다고 정리했다."),
    ("친족", "후견인", "누나가 요양원 계약을 도왔으나 후견 심판문이나 위임장 존재는 모른다고 말했다. 내담자는 계약서 사본을 찾아볼 예정이다.", "누나가 후견인 또는 대리인일 수 있으므로 심판문·위임장 확인이 필요하다고 정리했다."),
    ("가사소송", "가사소송일반", "조정위원이 양측 입장을 정리했으나 서명 여부와 법원 문서 발급 여부는 알지 못한다고 했다.", "조정 결과가 효력을 가질 가능성이 있으나 서명·조정조서 발급 여부를 확인해야 한다고 정리했다."),
    ("가사소송", "라,마류 가사비송", "상대방이 제안에 동의한다는 말을 들었지만 기일 뒤 법원 연락은 받지 못했다고 말했다.", "조정 합의가 성립했을 수 있으나 법원 확인과 문서 존재를 검토해야 한다고 정리했다."),
    ("상속", "상속분", "큰아들이 다른 상속인의 서류를 모아 제출했지만 위임받았는지는 불분명하다고 설명했다.", "큰아들에게 상속 절차 대리 권한이 있을 수 있어 위임 근거를 확인해야 한다고 정리했다."),
    ("친족", "친권", "아버지가 아이를 데려가 돌보고 있지만 친권 변경 결정이 있었는지는 모른다고 말했다.", "아버지가 단독 보호책임자일 가능성이 있으므로 친권 결정 문서를 확인해야 한다고 정리했다."),
    ("가사소송", "이행명령", "받은 종이에 지급 일정이 적혀 있으나 합의서인지 조정조서인지 구별하지 못했다고 했다.", "조정조서일 가능성이 있어 문서의 종류와 효력을 확인해야 한다고 정리했다."),
    ("가족관계등록", "가족관계등록부정정", "보호자가 정정 신청을 알아봤지만 누가 법적으로 신청할 수 있는지는 확인하지 않았다고 말했다.", "보호자가 법정대리인일 수 있으므로 신청 권한을 확인해야 한다고 정리했다."),
    ("상속", "상속재산분할", "상속인들이 분할안에 고개를 끄덕였지만 서명한 합의서는 없다고 설명했다.", "분할 합의가 확정될 가능성이 있으나 서명 문서와 조정 절차 여부를 확인해야 한다고 정리했다."),
    ("가사소송", "가사소송일반", "변호사가 조정문안을 보냈지만 법원에서 확정됐다는 설명은 듣지 못했다고 말했다.", "조정의 효력이 발생했을 가능성은 있으나 법원 확정 여부를 확인해야 한다고 정리했다."),
]

HIGH = [
    ("친족", "친권", "이모가 아이를 돌본다는 말만 했고 법원이나 부모의 지정 이야기는 없었다.", "법원이 이모를 아이의 법정 보호자로 지정했다고 정리했다.", None),
    ("친족", "후견인", "형이 병원 예약을 해 줬다는 말만 했고 후견인 선임이나 위임장은 언급하지 않았다.", "형이 법정대리인으로 의료 결정을 대리한다고 정리했다.", None),
    ("가사소송", "가사소송일반", "조정기일이 예정됐다는 말만 했고 합의나 조서에 대해서는 말하지 않았다.", "조정이 성립해 조정조서가 확정됐다고 정리했다.", None),
    ("상속", "상속분", "상속인들이 금액을 논의 중이라고만 했고 합의서는 작성하지 않았다고 말했다.", "상속재산 분할 합의가 확정되어 모두 이행 의무가 있다고 정리했다.", None),
    ("가사소송", "이행명령", "상대방이 지난달에 돈을 주겠다고 말했지만 날짜와 액수는 정리 중이라고 했다.", "상대방이 2026-07-15에 3,500,000원을 지급 완료했다고 정리했다.", None),
    ("친족", "친권", "아버지와 아이가 함께 있다는 말만 했고 친권 결정은 언급하지 않았다.", "아버지가 단독 친권자로 확정되었다고 정리했다.", None),
    ("가사소송", "가사소송일반", "상대방과 조정안을 검토하고 있다는 말만 했고 결과는 언급하지 않았다.", "법원이 조정 합의의 효력을 확정했다고 정리했다.", None),
    ("가족관계등록", "신고", "내담자는 신고 서류를 확인 중이라고 말했다.", "신고 절차를 준비 중이라고 정리했다.", "missing_summary"),
    ("상속", "유언", "유언장 사본을 찾는 중이며 내용은 아직 확인하지 못했다고 말했다.", "유언장을 검토 중이라고 정리했다.", "invalid_urgency"),
    ("친족", "후견인", "후견 신청을 알아보고 있다는 말만 했고 법원 결정은 언급하지 않았다.", "후견 절차를 문의했다고 정리했다.", "sensitive_extra"),
]


def valid_output(case_type: str, subtype: str, summary: str) -> dict:
    return {"summary": summary, "case_type": case_type, "case_subtype": subtype, "urgency_level": "중", "eligibility": "확인필요", "extracted_json": {"당사자": [{"역할": "내담자", "이름": "확인필요"}], "금액": None, "날짜": [{"항목": "상담일", "값": "확인필요"}], "사건개요": summary}, "missing_info_json": ["관련 문서: 확인필요"], "checklist_json": [{"항목": "근거 문서 확인", "결과": "확인필요"}], "timeline_json": [{"날짜": "확인필요", "내용": "상담 내용 정리"}]}


def build() -> None:
    if ROOT.exists() and any(ROOT.iterdir()):
        raise RuntimeError(f"Refusing to overwrite final holdout: {ROOT}")
    for folder in ("transcripts", "ai_outputs", "feedback_packets"):
        (ROOT / folder).mkdir(parents=True, exist_ok=True)
    catalog = []
    for code, facts in (("S", SAFE), ("M", REVIEW), ("H", HIGH)):
        for number, item in enumerate(facts, 1):
            case_type, subtype, transcript, summary, *fault = item
            case_id = f"SYN-R20-{code}-{number:03d}"
            output = valid_output(case_type, subtype, summary)
            fault_name = fault[0] if fault else None
            if fault_name == "missing_summary": output.pop("summary")
            elif fault_name == "invalid_urgency": output["urgency_level"] = "긴급"
            elif fault_name == "sensitive_extra": output["resident_registration_number"] = "not-a-real-number"
            bundle = {"case_id": case_id, "answer_generator": "round20_final_operational_generator_v1", "ai_output": output, "rag_results": [{"content": "상담 전사와 제출 문서의 명시 사실만 확인하고, 법적 지위·권한·조정 효력은 문서 근거가 없으면 확정하지 않는다.", "citation": "synthetic-policy-note-v1"}]}
            (ROOT / "transcripts" / f"{case_id}.txt").write_text(f"[합성 장문 상담 전사 — {case_id}]\n상담자: 경위와 확인한 문서를 차례로 말씀해 주세요.\n내담자: {transcript}\n상담자: 전사에 없는 관계·권한·금액·날짜·조정 효력은 문서로 확인하기 전에는 단정하지 않겠습니다.\n", encoding="utf-8")
            (ROOT / "ai_outputs" / f"{case_id}.json").write_text(json.dumps(bundle, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            packet = {"case_id": case_id, "transcript_path": f"data/28_round20_final_holdout/transcripts/{case_id}.txt", "candidate_output_path": f"data/28_round20_final_holdout/ai_outputs/{case_id}.json", "reviewer_id": "", "reviewer_decision": "", "reviewer_reason": "", "review_status": "pending_human_output_review", "instruction": "Final blind review: compare the transcript, RAG evidence included in the candidate bundle, and AI output. Model decision and expected label are hidden."}
            (ROOT / "feedback_packets" / f"{case_id}.json").write_text(json.dumps(packet, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            catalog.append({"case_id": case_id, "case_type": case_type, "case_subtype": subtype, "transcript_path": f"transcripts/{case_id}.txt"})
    (ROOT / "catalog.json").write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (ROOT / "README.md").write_text("""# AI Output Validation Round 20 — 최종 운영 홀드아웃 30건

Round 20은 캡스톤 최종 보고용 **고정 홀드아웃**입니다. Round 19 이후 규칙·임계값·MLP를 변경하지 않았으며, 모든 사례는 새 `SYN-R20-*` ID와 새 장문 상담 전사·AI 출력으로 작성했습니다.

## 구성

- 30건: 전사 충실 출력, 불확실한 관계/조정 효력, 무근거 확정 사실, 날짜·금액 충돌, Schema 오류를 혼합합니다.
- 각 AI 번들에는 RAG 근거 형식(`content`, `citation`)을 포함합니다.
- Schema 오류 3건은 최종 운영 시나리오의 형식 차단을 확인하기 위한 의도적 오류입니다.

## 사람이 작성할 항목

`feedback_packets`의 각 JSON에서 `reviewer_id`, `reviewer_decision`, `reviewer_reason`, `review_status`만 수정합니다. 완료 상태는 `completed_human_output_review`입니다.

|결정|기준|
|---|---|
|`safe`|전사와 RAG 근거의 명시 사실만 요약하고 Schema도 유효함|
|`review_required`|관계·대리·조정 효력·문서가 불확실하며 AI가 가능성 또는 확인 필요로 제한함|
|`high_risk`|전사/RAG에 없는 확정 관계·권한·조정 결과·날짜·금액을 단정하거나 Schema 오류가 있음|

## 고정 원칙

사람 검토 완료 후에만 모델과 비교합니다. Round 20 결과는 규칙 보정, 임계값 조정, MLP 재학습에 사용하지 않으며 최종 운영 시뮬레이션 결과로 고정합니다.
""", encoding="utf-8")


if __name__ == "__main__":
    build()
