"""Create a fresh, label-free 30-case output-validation batch for threshold confirmation."""

from __future__ import annotations

import json
from pathlib import Path


TOPICS = {
    "easy": [("친족", "협의이혼", "협의이혼 서류와 절차"), ("상속", "상속일반", "상속 순위와 기초 서류"), ("가족관계등록", "신고", "가족관계 신고 방법")],
    "medium": [("친족", "면접교섭권", "면접교섭 일정 이행"), ("상속", "상속분", "상속분 산정 다툼"), ("가사소송", "이행명령", "양육비 이행명령")],
    "hard": [("친족", "이혼 및 재산분할청구권", "재산과 채무가 섞인 이혼"), ("상속", "유류분", "증여 재산이 있는 유류분"), ("가족관계등록", "가족관계등록부정정", "등록부 기재 정정")],
}


def build(root: Path) -> None:
    catalog = []
    for difficulty, code in (("easy", "E"), ("medium", "M"), ("hard", "H")):
        for number in range(1, 11):
            case_id = f"SYN-R3-{code}-{number:03d}"
            case_type, subtype, topic = TOPICS[difficulty][(number - 1) % 3]
            transcript = f"""[신규 합성 상담 전사 / {case_id}]
내담자: {topic} 때문에 상담을 신청했습니다. 2025년 {number}월부터 관련 상황이 이어지고 있습니다.
상담자: 현재 확인 가능한 자료가 있나요?
내담자: 문자 또는 통화기록 일부와 신분관계 서류를 보관하고 있습니다. 금액과 정확한 날짜는 아직 정리 중입니다.
상담자: 요청하시는 도움은 무엇인가요?
내담자: {subtype}와 관련해 가능한 절차 및 추가 확인 자료를 알고 싶습니다. 확정되지 않은 사실은 확인 후 제출하겠습니다.
"""
            transcript_rel = f"transcripts/{case_id}.txt"
            (root / transcript_rel).parent.mkdir(parents=True, exist_ok=True)
            (root / transcript_rel).write_text(transcript, encoding="utf-8")
            catalog.append({"case_id": case_id, "difficulty": difficulty, "case_type": case_type, "case_subtype": subtype, "transcript_path": transcript_rel})
    (root / "catalog.json").write_text(json.dumps(catalog, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    build(Path("data/10_round3"))
    print("Created 30 fresh round-3 source transcripts")
