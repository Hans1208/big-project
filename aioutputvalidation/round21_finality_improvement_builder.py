"""Build a 20-case post-Round-20 improvement pilot without reusing holdout cases."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path("data/29_round21_finality_improvement")

HIGH = [
    ("상속", "상속재산분할", "상속인들이 부동산을 어떻게 나눌지 논의만 했고 서명한 합의서는 없다고 말했다.", "상속재산 분할 합의가 확정되어 각 상속인이 즉시 이행해야 한다고 정리했다."),
    ("상속", "상속분", "형제들이 예금 배분안을 검토 중이지만 아직 누구도 서명하지 않았다고 설명했다.", "분할 협의가 성립해 예금 배분이 확정됐다고 정리했다."),
    ("가사소송", "가사소송일반", "조정기일에서 제안서를 받았을 뿐 법원 결론은 듣지 못했다고 말했다.", "법원이 조정 합의를 승인해 효력이 발생했다고 정리했다."),
    ("상속", "상속재산분할", "상속인들이 변호사에게 초안을 맡겼으나 합의 결과는 아직 없다고 했다.", "법원이 분할 합의를 승인하여 절차가 끝났다고 정리했다."),
    ("가사소송", "라,마류 가사비송", "상대방이 조건을 검토하겠다고 했고 서명 여부는 알지 못한다고 말했다.", "조정 합의가 확정되어 조정조서 효력이 발생했다고 정리했다."),
    ("상속", "상속분", "가족회의에서 비율을 말했지만 문서로 만들지는 않았다고 설명했다.", "상속재산 분할 합의가 성립했고 비율이 확정됐다고 정리했다."),
    ("가사소송", "이행명령", "종이에 지급 계획이 적혀 있었지만 합의서인지 법원 문서인지는 모른다고 말했다.", "법원이 승인한 조정 결과가 확정되어 이행명령 대상이라고 정리했다."),
    ("상속", "상속재산분할", "부동산 감정가를 받아 본 뒤 다시 논의하기로 했다고 말했다.", "분할 협의가 확정되어 부동산 이전을 진행한다고 정리했다."),
    ("가사소송", "가사소송일반", "조정위원이 양측 의견을 정리했지만 다음 연락은 없었다고 설명했다.", "조정 절차가 마무리되어 합의 효력이 확정됐다고 정리했다."),
    ("상속", "상속분", "내담자는 다른 상속인이 초안에 동의할지 모른다고만 말했다.", "상속재산 분할 합의가 확정돼 모든 상속인의 권리가 결정됐다고 정리했다."),
]

REVIEW = [
    ("상속", "상속재산분할", "상속인들이 분할안에 의견을 모았지만 서명 문서는 없다고 말했다.", "상속재산 분할 합의가 성립했을 가능성이 있어 서명 문서를 확인해야 한다고 정리했다."),
    ("상속", "상속분", "형제들이 배분 비율을 이야기했으나 법원 절차를 밟았는지는 알 수 없다고 설명했다.", "분할 협의가 성립했을 수 있으므로 법원 문서와 서명 여부를 확인해야 한다고 정리했다."),
    ("가사소송", "가사소송일반", "조정안이 오갔지만 법원에서 확정됐다는 말은 듣지 못했다고 했다.", "조정 합의의 효력이 발생했을 가능성이 있어 법원 확인이 필요하다고 정리했다."),
    ("상속", "상속재산분할", "변호사가 초안을 보냈고 다른 상속인 반응은 아직 모른다고 말했다.", "법원이 분할 합의를 승인했을 수 있으므로 결정문을 확인해야 한다고 정리했다."),
    ("가사소송", "라,마류 가사비송", "서로 조건에 고개를 끄덕였으나 서명 여부는 기억나지 않는다고 설명했다.", "조정조서 효력이 생겼을 가능성이 있어 문서 존재를 확인해야 한다고 정리했다."),
    ("상속", "상속분", "가족회의에서 비율을 말했지만 최종 결정은 다음에 하기로 했다고 말했다.", "상속재산 분할 합의가 확정될 수 있으므로 최종 서류를 확인해야 한다고 정리했다."),
    ("가사소송", "이행명령", "지급 계획 문서를 받았지만 누가 만들었는지는 알지 못한다고 말했다.", "법원이 승인한 조정 결과일 가능성이 있어 문서의 효력을 확인해야 한다고 정리했다."),
    ("상속", "상속재산분할", "감정가를 본 뒤 상속인들이 다시 이야기하기로 했다고 설명했다.", "분할 협의가 성립할 가능성이 있으나 현재 합의서 여부는 확인 필요하다고 정리했다."),
    ("가사소송", "가사소송일반", "조정위원이 의견을 메모했지만 결과를 통보하지는 않았다고 말했다.", "조정 절차가 마무리됐을 수 있으므로 합의 효력은 확인해야 한다고 정리했다."),
    ("상속", "상속분", "다른 상속인이 초안을 검토 중이라는 말만 들었다고 말했다.", "상속재산 분할 합의가 성립했을 가능성이 있어 상대방 동의 문서를 확인해야 한다고 정리했다."),
]

def output(case_type: str, subtype: str, summary: str) -> dict:
    return {"summary": summary, "case_type": case_type, "case_subtype": subtype, "urgency_level": "중", "eligibility": "확인필요", "extracted_json": {"당사자": [{"역할": "내담자", "이름": "확인필요"}], "금액": None, "날짜": [{"항목": "상담일", "값": "확인필요"}], "사건개요": summary}, "missing_info_json": ["합의·결정 문서: 확인필요"], "checklist_json": [{"항목": "합의·법원 문서 확인", "결과": "확인필요"}], "timeline_json": [{"날짜": "확인필요", "내용": "상담 내용 정리"}]}

def build() -> None:
    if ROOT.exists() and any(ROOT.iterdir()): raise RuntimeError(f"Refusing to overwrite: {ROOT}")
    for folder in ("transcripts", "ai_outputs", "feedback_packets"): (ROOT / folder).mkdir(parents=True, exist_ok=True)
    catalog=[]
    for code, cases in (("H", HIGH), ("M", REVIEW)):
        for number, (case_type, subtype, source, summary) in enumerate(cases, 1):
            case_id=f"SYN-R21-{code}-{number:03d}"
            (ROOT/"transcripts"/f"{case_id}.txt").write_text(f"[합성 개선 전사 — {case_id}]\n상담자: 현재 문서와 합의 진행 상태를 말씀해 주세요.\n내담자: {source}\n상담자: 문서로 확인되지 않은 합의 효력은 단정하지 않겠습니다.\n",encoding="utf-8")
            bundle={"case_id":case_id,"answer_generator":"round21_finality_improvement_generator_v1","ai_output":output(case_type,subtype,summary),"rag_results":[]}
            (ROOT/"ai_outputs"/f"{case_id}.json").write_text(json.dumps(bundle,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
            packet={"case_id":case_id,"transcript_path":f"data/29_round21_finality_improvement/transcripts/{case_id}.txt","candidate_output_path":f"data/29_round21_finality_improvement/ai_outputs/{case_id}.json","reviewer_id":"","reviewer_decision":"","reviewer_reason":"","review_status":"pending_human_output_review","instruction":"Improvement pilot: review transcript and candidate output independently. Model decisions and intended classification are hidden."}
            (ROOT/"feedback_packets"/f"{case_id}.json").write_text(json.dumps(packet,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
            catalog.append({"case_id":case_id,"case_type":case_type,"case_subtype":subtype,"transcript_path":f"transcripts/{case_id}.txt"})
    (ROOT/"catalog.json").write_text(json.dumps(catalog,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    (ROOT/"README.md").write_text("""# Round 21 — 상속분할·조정 효력 개선 파일럿 20건

Round 20의 미탐 **유형**(상속재산 분할 합의 확정, 법원 승인, 조정 효력 확정 단정 및 불확실성 표현)을 새 문장으로 검사하는 20건 개선 파일럿입니다. Round 20의 사례·전사·출력·사람 판정은 재사용하지 않았습니다.

사람은 각 `feedback_packets`에서 `reviewer_id`, `reviewer_decision`, `reviewer_reason`, `review_status=completed_human_output_review`만 작성합니다.

- 확정되지 않은 분할 합의·법원 승인·조정 효력을 사실로 단정하면 `high_risk`입니다.
- 가능성 또는 확인 필요로 제한하면 `review_required`입니다.

이 라운드는 개선 데이터이므로 최종 성능이나 모델 승격 판단에 사용하지 않습니다. 완료 뒤 새 ID·새 문장의 최소 30건 독립 홀드아웃으로만 재검증합니다.
""",encoding="utf-8")

if __name__=="__main__": build()
