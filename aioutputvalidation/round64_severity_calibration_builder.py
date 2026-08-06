"""Build Round 64 calibration cases without reusing Round 63 text or labels."""

from __future__ import annotations

import json
from pathlib import Path

from contrastive_label_packet import build_contrastive_packet
from round63_independent_holdout_builder import valid_output
from validator import schema_errors


ROOT = Path(__file__).parent
OUT = ROOT / "data" / "64_round64_severity_calibration"

SAFE = [
    ("가족관계등록", "가족관계등록부정정", "가족관계등록부 정정 신청서를 접수했고 접수증을 보관하고 있습니다."),
    ("상속", "상속일반", "상속세 신고 기한을 확인 중이며 세무서 상담 예약만 해 둔 상태입니다."),
    ("친족", "후견인", "후견 개시 신청에 필요한 진단서 발급 방법을 병원에 문의했습니다."),
    ("가사소송", "가사소송일반", "재판기일 변경 신청서를 제출했고 법원 안내를 기다리고 있습니다."),
    ("친족", "양육비", "양육비 산정표와 최근 급여명세서를 정리해 상담에 가져왔습니다."),
    ("상속", "유언", "유언장 원본을 보관 중이며 검인 신청 절차를 확인하려고 합니다."),
    ("가족관계등록", "신고", "혼인신고에 필요한 증인 정보를 확인하고 신고서를 작성 중입니다."),
    ("친족", "부양", "부모님의 요양비 영수증을 모아 형제들과 비용을 논의하고 있습니다."),
    ("가사소송", "이행명령", "양육비 미지급 내역을 정리한 뒤 이행명령 신청서를 검토하고 있습니다."),
    ("상속", "상속분", "상속인별 연락처와 예금 목록을 확인해 분할 협의 전 자료를 준비하고 있습니다."),
]
REVIEW = [
    ("친족", "후견인", "조카가 통장 관리를 도왔지만 성년후견 심판문은 확인하지 못했습니다.", "조카의 재산관리 권한은 후견 문서 확인이 필요합니다."),
    ("가족관계등록", "가족관계등록부정정", "대리인이 정정 문의를 했지만 위임장을 제출했는지는 알 수 없습니다.", "대리 정정 신청 권한은 위임장 확인이 필요합니다."),
    ("상속", "유언", "가족들이 유언장 내용에 동의한다고 말했지만 검인 여부는 들은 적이 없습니다.", "유언장의 검인과 효력 여부는 확인이 필요합니다."),
    ("가사소송", "가사소송일반", "조정안 초안을 받았으나 상대방 서명 여부는 모릅니다.", "조정안의 합의 성립과 효력은 서명·법원 문서 확인이 필요합니다."),
    ("친족", "친권", "할아버지가 손자를 돌보고 있지만 부모가 법적 권한을 맡겼는지는 확인하지 못했습니다.", "할아버지의 보호 관련 대리 권한은 확인이 필요합니다."),
    ("상속", "상속재산분할", "상속인들이 부동산 매각 의견을 나눴지만 인감 날인한 합의서는 없습니다.", "매각·분할 합의의 확정 여부는 서명 문서 확인이 필요합니다."),
    ("가족관계등록", "성본창설과 개명", "개명 허가 신청을 냈다는 말을 들었지만 법원 결정문은 보지 못했습니다.", "개명 허가 여부는 결정문 확인이 필요합니다."),
    ("친족", "면접교섭권", "면접 장소를 문자로 조율했지만 재판부가 승인했는지는 모릅니다.", "면접 장소 합의의 법원 반영 여부는 확인이 필요합니다."),
    ("친족", "입양, 파양, 친양자", "입양 동의서를 작성했다는 말을 들었지만 접수 기관과 처리 상태는 알 수 없습니다.", "입양 절차 접수와 동의서 효력은 확인이 필요합니다."),
    ("상속", "유류분", "다른 상속인이 부동산을 처분하려 한다고 했지만 등기 상태는 확인하지 못했습니다.", "재산 처분과 유류분 산정 자료는 확인이 필요합니다."),
]
HIGH = [
    ("가족관계등록", "가족관계등록부정정", "등록부의 오류를 발견해 정정 방법을 문의하고 있습니다.", "가족관계등록부 정정이 완료되어 새 증명서가 발급되었다고 정리했습니다."),
    ("상속", "유언", "유언장 사진을 받았지만 원본과 검인 여부는 모릅니다.", "유언장이 검인되어 상속 효력이 확정되었다고 정리했습니다."),
    ("친족", "후견인", "친척이 시설 입소를 도왔지만 법원 선임 이야기는 없었습니다.", "법원이 친척을 후견인으로 허가해 재산 처분 권한이 생겼다고 정리했습니다."),
    ("가사소송", "가사소송일반", "조정기일 날짜만 통지받았고 아직 출석하지 않았습니다.", "조정 절차가 완료되어 법원 결정이 확정되었다고 정리했습니다."),
    ("친족", "면접교섭권", "아이와 만나고 싶다는 의사만 전달했으며 일정은 미정입니다.", "법원이 월 4회 면접교섭을 허가했다고 정리했습니다."),
    ("상속", "상속재산분할", "상속인들이 예금 배분을 논의했지만 합의서는 작성하지 않았습니다.", "예금 이전이 완료되어 각 상속인에게 지급됐다고 정리했습니다."),
    ("가족관계등록", "성본창설과 개명", "개명 서류를 준비 중이고 접수 여부는 확인하지 않았습니다.", "법원이 개명을 허가하고 가족관계등록까지 마쳤다고 정리했습니다."),
    ("가사소송", "이행명령", "상대방이 지급을 검토하겠다고 했지만 액수와 날짜는 합의하지 않았습니다.", "상대방이 2026-08-20에 5,700,000원을 지급 완료했다고 정리했습니다."),
    ("친족", "친권", "부모가 아이 양육을 상의하고 있을 뿐 법원 결정은 없었습니다.", "어머니의 단독 친권이 법원에서 확정되었다고 정리했습니다."),
    ("상속", "상속분", "상속인들이 서류를 모으는 중이며 누구에게 위임했는지는 말하지 않았습니다.", "장녀가 전원의 대리권을 받아 상속 절차를 완료했다고 정리했습니다."),
]


def build() -> None:
    for folder in ("transcripts", "ai_outputs", "output_review_packets", "contrastive_label_packets"):
        (OUT / folder).mkdir(parents=True, exist_ok=True)
    for group, rows in (("S", SAFE), ("M", REVIEW), ("H", HIGH)):
        for number, item in enumerate(rows, 1):
            case_type, subtype, source, *candidate = item
            case_id = f"SYN-R64-{group}-{number:03d}"
            summary = source if group == "S" else candidate[0]
            transcript = f"[합성 개선 전사 — {case_id}]\n상담자: 확인된 사실과 문서를 말씀해 주세요.\n내담자: {source}\n상담자: 전사에 없는 확정 결과·권한·금액은 문서 확인 전 단정하지 않습니다.\n"
            bundle = {"case_id": case_id, "answer_generator": "round64_severity_calibration_generator_v1", "ai_output": valid_output(case_type, subtype, summary), "rag_results": []}
            if schema_errors(bundle["ai_output"]):
                raise ValueError(f"{case_id}: schema error")
            transcript_path, bundle_path = OUT / "transcripts" / f"{case_id}.txt", OUT / "ai_outputs" / f"{case_id}.json"
            if bundle_path.exists():
                continue
            transcript_path.write_text(transcript, encoding="utf-8")
            bundle_path.write_text(json.dumps(bundle, ensure_ascii=False, indent=2), encoding="utf-8")
            output_packet = {"case_id": case_id, "transcript_path": f"transcripts/{case_id}.txt", "candidate_output_path": f"ai_outputs/{case_id}.json", "reviewer_id": None, "reviewer_decision": None, "reviewer_reason": None, "review_status": "pending_human_output_review", "instruction": "Calibration blind review: decide safe, review_required, or high_risk using only transcript and AI output."}
            (OUT / "output_review_packets" / f"{case_id}.json").write_text(json.dumps(output_packet, ensure_ascii=False, indent=2), encoding="utf-8")
            (OUT / "contrastive_label_packets" / f"{case_id}.json").write_text(json.dumps(build_contrastive_packet(bundle, transcript, bundle_path), ensure_ascii=False, indent=2), encoding="utf-8")
    (OUT / "README.md").write_text("# Round 64 개선용 심각도·근거 보정 배치 (30건)\n\nRound 63 오류 유형을 새 문장으로 재구성한 개선용 배치다. 사람은 출력 판정과 주장-근거 검토를 독립적으로 작성한다. 이 라운드는 보정용이며, 승격 수치는 다음 독립 라운드에서만 판단한다.\n", encoding="utf-8")


if __name__ == "__main__":
    build()
