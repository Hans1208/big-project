"""Create role-separated fictional consultation sources up to 45 balanced cases."""

from __future__ import annotations

import json
from pathlib import Path


BLUEPRINTS = {
    "easy": [
        ("친족", "협의이혼", "협의이혼 절차와 준비 서류"), ("상속", "상속일반", "부친 사망 후 상속 순위 확인"),
        ("가족관계등록", "신고", "출생신고 기한과 방법"), ("친족", "양육비", "양육비 지급 약속 불이행"),
        ("상속", "유언", "자필 유언장 보관 방법"), ("가족관계등록", "성본창설과 개명", "미성년 자녀 개명 가능 여부"),
    ],
    "medium": [
        ("친족", "면접교섭권", "면접교섭 일정이 지켜지지 않는 문제"), ("상속", "상속분", "형제자매 간 법정상속분 다툼"),
        ("친족", "후견인", "치매 가족의 성년후견 신청"), ("상속", "상속재산분할", "부동산을 포함한 상속재산 분할"),
        ("친족", "친권", "이혼 뒤 친권자 변경 가능성"), ("가사소송", "이행명령", "양육비 이행명령 신청 여부"),
    ],
    "hard": [
        ("친족", "이혼 및 재산분할청구권", "사업체와 대출이 섞인 재산분할"), ("상속", "유류분", "증여 재산이 있는 유류분 반환"),
        ("가족관계등록", "가족관계등록부정정", "가족관계등록부 생년월일 정정"), ("친족", "재판상이혼 등", "장기간 별거와 폭언이 있는 이혼"),
        ("상속", "상속재산분할", "해외 재산과 채무가 함께 있는 상속"), ("가사소송", "양육비직접지급명령", "급여 압류 전 직접지급명령 검토"),
    ],
}


def make_transcript(case_id: str, difficulty: str, case_type: str, subtype: str, topic: str, index: int) -> str:
    names = [("서윤", "민호"), ("지안", "도윤"), ("하린", "준서"), ("유진", "시우"), ("수아", "현우"), ("예린", "태윤")]
    caller, related = names[index % len(names)]
    dates = ("2025년 3월", "2025년 5월", "2025년 7월", "2025년 10월")
    date = dates[index % len(dates)]
    uncertainty = "정확한 날짜와 관련 서류의 원본 보유 여부는 아직 확인하지 못했습니다." if difficulty != "easy" else "일부 서류는 준비 중입니다."
    return f"""[합성 상담 전사본 / {case_id} / {difficulty}]
상담자: 안녕하세요. {topic} 때문에 문의드립니다.
내담자 {caller}: {date}부터 관련 문제가 이어졌습니다. 상대방 또는 관련인은 {related}이며, 현재 제가 가진 정보로 절차를 확인하고 싶습니다.
상담자: 어떤 자료가 있으신가요?
내담자 {caller}: 문자·통화 기록 일부와 신분관계 확인 서류를 가지고 있습니다. 금전과 재산 문제는 정확한 금액을 정리 중입니다. {uncertainty}
상담자: 현재 요청하시는 도움은 무엇인가요?
내담자 {caller}: {subtype} 관련으로 가능한 절차와 추가로 확인할 자료를 알고 싶습니다. 사실관계가 더 필요하면 확인 후 제출하겠습니다.
"""


def expand(data_root: Path, target_per_difficulty: int = 15) -> list[dict]:
    catalog_path = data_root / "scenario_catalog.json"
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    for difficulty, code in (("easy", "E"), ("medium", "M"), ("hard", "H")):
        existing = [item for item in catalog if item["difficulty"] == difficulty]
        for number in range(len(existing) + 1, target_per_difficulty + 1):
            case_type, subtype, topic = BLUEPRINTS[difficulty][(number - 4) % len(BLUEPRINTS[difficulty])]
            case_id = f"SYN-{code}-{number:03d}"
            transcript_rel = f"02_transcripts/{case_id}.txt"
            spec_rel = f"01_case_specs/{case_id}.md"
            transcript = make_transcript(case_id, difficulty, case_type, subtype, topic, number)
            (data_root / transcript_rel).write_text(transcript, encoding="utf-8")
            (data_root / spec_rel).write_text(f"# {case_id}\n\n- 난이도: {difficulty}\n- 유형: {case_type} / {subtype}\n- 주제: {topic}\n- 데이터 역할: 사건 시나리오(정답 라벨과 분리)\n", encoding="utf-8")
            catalog.append({"case_id": case_id, "difficulty": difficulty, "case_type": case_type, "case_subtype": subtype, "spec_path": spec_rel, "transcript_path": transcript_rel})
    catalog_path.write_text(json.dumps(catalog, ensure_ascii=False, indent=2), encoding="utf-8")
    return catalog


if __name__ == "__main__":
    result = expand(Path("data"))
    print(f"Expanded catalog to {len(result)} cases")
