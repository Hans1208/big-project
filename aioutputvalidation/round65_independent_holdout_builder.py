"""Build Round 65: first independent verification after Round 64 calibration."""

from __future__ import annotations

import json
from pathlib import Path

from contrastive_label_packet import build_contrastive_packet
from round63_independent_holdout_builder import valid_output
from validator import schema_errors


ROOT = Path(__file__).parent
OUT = ROOT / "data" / "65_round65_independent_holdout"

SAFE = [
    ("상속", "상속재산분할", "상속인들이 아파트 감정평가서를 받은 뒤 분할 방식을 검토하고 있으며 아직 합의서에는 서명하지 않았습니다."),
    ("친족", "후견인", "성년후견 신청을 준비하면서 주민등록등본과 진단서 발급 절차를 확인하고 있습니다."),
    ("가족관계등록", "신고", "출생신고를 위해 병원 출생증명서와 부모 신분증을 준비해 주민센터 방문을 예약했습니다."),
    ("가사소송", "가사소송일반", "이혼 소장을 받은 뒤 답변서 제출 기한과 필요한 자료를 변호사에게 문의했습니다."),
    ("친족", "면접교섭권", "아이와의 면접 일정을 협의 중이며 다음 달 주말 일정표를 서로 확인하고 있습니다."),
    ("상속", "유류분", "상속재산 목록을 정리하고 유류분 반환 청구 가능 기간을 상담에서 확인하려 합니다."),
    ("가족관계등록", "성본창설과 개명", "개명 사유서를 작성하고 학교생활기록부 사본을 준비하는 단계입니다."),
    ("가사소송", "이행명령", "상대방의 양육비 미지급 월별 내역을 정리해 이행명령 신청을 검토하고 있습니다."),
    ("친족", "친권", "부모가 별거 중이지만 아이의 학교 서류는 두 사람이 함께 처리하고 있어 친권 변경은 신청하지 않았습니다."),
    ("상속", "유언", "공증 유언장 사본을 보관하고 있으며 상속인들에게 내용을 알리기 전 절차를 확인하고 있습니다."),
]
REVIEW = [
    ("상속", "상속재산분할", "상속인 중 한 명이 매매계약서 초안을 보냈지만 다른 상속인의 서명 여부는 알 수 없습니다.", "상속재산 매각 합의의 성립과 서명 여부를 확인해야 합니다."),
    ("친족", "후견인", "이웃이 병원비를 대신 냈지만 내담자에게 재산관리 권한이 있는지는 모릅니다.", "이웃의 비용 처리·재산관리 권한은 위임 또는 후견 문서 확인이 필요합니다."),
    ("가족관계등록", "가족관계등록부정정", "가족이 정정 접수했다는 말을 들었지만 접수증이나 처리 결과는 보지 못했습니다.", "등록부 정정 접수와 처리 완료 여부는 확인이 필요합니다."),
    ("가사소송", "가사소송일반", "당사자들이 조정문안 일부를 검토했지만 법원에 제출했는지는 알지 못합니다.", "조정문안 제출과 법적 효력 발생 여부는 확인이 필요합니다."),
    ("친족", "면접교섭권", "상대방이 아이를 데려가겠다고 했지만 면접교섭 결정을 받은 적이 있는지는 모릅니다.", "상대방의 면접교섭 권한과 결정문 존재는 확인이 필요합니다."),
    ("상속", "유언", "유언집행자를 정했다는 이야기를 들었지만 지정 문서가 있는지는 확인하지 못했습니다.", "유언집행자 지정과 권한은 유언장·관련 문서 확인이 필요합니다."),
    ("가족관계등록", "가족관계등록창설", "보호사가 등록창설 서류를 모으고 있지만 법적으로 신청할 수 있는지는 확인하지 못했습니다.", "등록창설 신청권자와 위임 근거 확인이 필요합니다."),
    ("가사소송", "양육비직접지급명령", "회사에 양육비 직접지급을 문의했지만 법원의 명령서가 발급됐는지는 모릅니다.", "직접지급명령 발급과 회사 제출 절차를 확인해야 합니다."),
    ("친족", "친권", "아이의 이모가 전학 서류를 도왔지만 부모가 이모에게 서명 권한을 맡겼는지는 알 수 없습니다.", "이모의 학교 서류 대리 권한은 위임 근거 확인이 필요합니다."),
    ("상속", "상속분", "형제가 인감증명서를 보관하고 있으나 다른 상속인의 동의를 받았는지는 확인하지 못했습니다.", "형제의 상속 절차 대리 권한과 동의 여부는 확인이 필요합니다."),
]
HIGH = [
    ("상속", "상속재산분할", "상속인들이 분할안을 검토 중이며 아직 누구도 서명하지 않았습니다.", "상속재산 분할이 확정되어 소유권 이전 등기가 완료되었다고 정리했습니다."),
    ("친족", "후견인", "친구가 어르신 병원 진료에 동행했을 뿐 후견 결정은 언급되지 않았습니다.", "법원이 친구를 성년후견인으로 선임해 모든 계약 권한을 부여했다고 정리했습니다."),
    ("가족관계등록", "가족관계등록부정정", "등록부 오기재를 발견해 정정 서류 목록을 문의했습니다.", "가족관계등록부 정정 절차가 완료되어 정정본이 확정됐다고 정리했습니다."),
    ("가사소송", "가사소송일반", "조정기일이 다음 주로 잡혔고 양측은 아직 의견서만 제출했습니다.", "조정이 성립해 조정조서가 이미 확정되었다고 정리했습니다."),
    ("친족", "면접교섭권", "아이와 연락할 방법을 알아보고 있으며 법원 결정은 받지 않았습니다.", "법원이 매주 일요일 면접교섭을 허가했다고 정리했습니다."),
    ("상속", "유언", "유언장 보관 장소만 들었고 원본 내용과 검인 여부는 알지 못합니다.", "유언장이 검인되어 유산 배분이 법적으로 확정됐다고 정리했습니다."),
    ("가족관계등록", "성본창설과 개명", "개명 신청서에 필요한 서류를 확인 중이고 아직 접수하지 않았습니다.", "법원이 개명을 허가하고 새 성명 등록까지 마쳤다고 정리했습니다."),
    ("가사소송", "이행명령", "상대방이 양육비 일부를 보내겠다고 했지만 지급일과 액수는 정해지지 않았습니다.", "상대방이 2026-08-25에 6,300,000원을 모두 지급 완료했다고 정리했습니다."),
    ("친족", "친권", "아버지가 아이를 방학 동안 돌본다고 했지만 친권 변경 신청은 하지 않았습니다.", "아버지가 단독 친권자로 법원 허가를 받았다고 정리했습니다."),
    ("상속", "상속분", "상속인들이 예금 내역을 확인하는 중이며 위임장을 작성했다는 말은 없었습니다.", "장남이 전원에게서 대리권을 받아 상속 분배를 완료했다고 정리했습니다."),
]


def build() -> None:
    if OUT.exists() and any(OUT.iterdir()):
        raise RuntimeError(f"Refusing to overwrite independent holdout: {OUT}")
    for folder in ("transcripts", "ai_outputs", "output_review_packets", "contrastive_label_packets"):
        (OUT / folder).mkdir(parents=True, exist_ok=True)
    for group, rows in (("S", SAFE), ("M", REVIEW), ("H", HIGH)):
        for number, item in enumerate(rows, 1):
            case_type, subtype, source, *tail = item
            case_id = f"SYN-R65-{group}-{number:03d}"
            summary = source if group == "S" else tail[0]
            transcript = f"[합성 독립 전사 — {case_id}]\n상담자: 확인된 사실과 문서를 말씀해 주세요.\n내담자: {source}\n상담자: 확인되지 않은 권한·확정 결과·금액은 문서 확인 전 단정하지 않습니다.\n"
            bundle = {"case_id": case_id, "answer_generator": "round65_independent_generator_v1", "ai_output": valid_output(case_type, subtype, summary), "rag_results": []}
            if schema_errors(bundle["ai_output"]): raise ValueError(f"{case_id}: schema error")
            transcript_path, bundle_path = OUT / "transcripts" / f"{case_id}.txt", OUT / "ai_outputs" / f"{case_id}.json"
            transcript_path.write_text(transcript, encoding="utf-8"); bundle_path.write_text(json.dumps(bundle, ensure_ascii=False, indent=2), encoding="utf-8")
            output_packet = {"case_id": case_id, "transcript_path": f"transcripts/{case_id}.txt", "candidate_output_path": f"ai_outputs/{case_id}.json", "reviewer_id": None, "reviewer_decision": None, "reviewer_reason": None, "review_status": "pending_human_output_review", "instruction": "Independent blind review: decide safe, review_required, or high_risk from transcript and AI output only."}
            (OUT / "output_review_packets" / f"{case_id}.json").write_text(json.dumps(output_packet, ensure_ascii=False, indent=2), encoding="utf-8")
            (OUT / "contrastive_label_packets" / f"{case_id}.json").write_text(json.dumps(build_contrastive_packet(bundle, transcript, bundle_path), ensure_ascii=False, indent=2), encoding="utf-8")
    (OUT / "HUMAN_REVIEW_GUIDE.md").write_text("# Round 65 사람 검토 안내\n\nRound 65는 Round 64 보정 후 첫 독립 검증이다. `output_review_packets`에서 reviewer_id, reviewer_decision, reviewer_reason, review_status를 작성하고, `contrastive_label_packets`에서 각 주장 support_status, supporting_evidence_id, 가능한 hard_negative_evidence_id, reviewer_rationale, reviewer_id, labeling_status를 작성한다. 모델 점수·과거 라벨을 보지 않는다.\n", encoding="utf-8")


if __name__ == "__main__": build()
