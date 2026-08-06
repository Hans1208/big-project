"""Add unlabeled contrastive challenge claims without overwriting human labels.

The injected statement is intentionally not present in its transcript, but that fact is
never stored in the packet. A human reviewer remains the only source of its label.
"""

from __future__ import annotations

import json
from pathlib import Path

from integration import extract_claims


CHALLENGES = {
    # Fixed v1 train cases
    "SYN-E-005": "상대방이 이미 이혼에 서면 동의했다.",
    "SYN-E-008": "상담자는 법원 접수까지 완료했다.",
    "SYN-H-004": "공동재산의 정확한 평가액은 3억 원이다.",
    # Fixed v1 validation cases
    "SYN-E-006": "상대방은 2024년 1월 15일에 모든 서류를 수령했다.",
    "SYN-E-009": "내담자는 과거 동일 사건에서 승소 판결을 받았다.",
    "SYN-E-012": "상대방은 양육비를 12개월 연체했다.",
    "SYN-H-005": "고인의 모든 재산은 이미 특정 상속인에게 증여되었다.",
    "SYN-H-008": "가족관계등록부 정정 신청은 이미 기각되었다.",
    "SYN-H-010": "상대방은 폭언 사실을 서면으로 인정했다.",
    # Fixed v1 test cases
    "SYN-E-004": "당사자들은 2023년 12월에 이미 합의서를 작성했다.",
    "SYN-E-007": "관련 신고는 법정기한을 이미 넘겼다.",
    "SYN-H-007": "해외 재산의 정확한 시가는 5억 원이다.",
    "SYN-H-013": "급여 지급자는 직접지급명령에 동의했다.",
}


def inject(bundle: dict, packet: dict, statement: str) -> bool:
    timeline = bundle["ai_output"].setdefault("timeline_json", [])
    if not any(item.get("내용") == statement for item in timeline if isinstance(item, dict)):
        timeline.append({"날짜": "확인필요", "내용": statement})
    claims = extract_claims(bundle["ai_output"])
    existing = {claim["claim_id"] for claim in packet["claims"]}
    added = False
    for index, text in enumerate(claims, start=1):
        claim_id = f"{packet['case_id']}-C{index:02d}"
        if claim_id not in existing:
            packet["claims"].append({"claim_id": claim_id, "text": text, "is_supported": None, "is_hallucination": None, "evidence_ids": [], "reviewer_rationale": None})
            added = True
    if added:
        packet["labeling_status"] = "pending_human_review"
    return added


if __name__ == "__main__":
    bundle_dir = Path("data/03_ai_outputs/generated")
    packet_dir = Path("data/04_gold_labels/label_packets")
    added_cases: list[str] = []
    for case_id, statement in CHALLENGES.items():
        bundle_path, packet_path = bundle_dir / f"{case_id}.json", packet_dir / f"{case_id}.json"
        bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
        packet = json.loads(packet_path.read_text(encoding="utf-8"))
        changed = inject(bundle, packet, statement)
        bundle_path.write_text(json.dumps(bundle, ensure_ascii=False, indent=2), encoding="utf-8")
        packet_path.write_text(json.dumps(packet, ensure_ascii=False, indent=2), encoding="utf-8")
        if changed:
            added_cases.append(case_id)
    print(json.dumps({"challenge_cases_requiring_human_review": added_cases, "count": len(added_cases)}, ensure_ascii=False))
