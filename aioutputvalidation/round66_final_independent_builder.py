"""Build the final independent confirmation batch without reusing Round 65 text."""

from __future__ import annotations

import json
from pathlib import Path

from contrastive_label_packet import build_contrastive_packet
from round63_independent_holdout_builder import valid_output
from validator import schema_errors


ROOT = Path(__file__).parent
OUT = ROOT / "data" / "66_round66_final_independent"

SAFE = [
    ("가족관계등록", "가족관계등록부정정", "가족관계증명서의 한자 표기를 확인해 정정 신청에 필요한 서류 목록을 메모하고 있습니다."),
    ("상속", "상속일반", "상속 개시 후 남은 예금과 대출 내역을 조회하고 있으며 상속포기 여부는 아직 가족과 상의 중입니다."),
    ("친족", "부양", "형제들이 부모님 간병비 영수증을 모아 다음 달 분담 방식을 논의하기로 했습니다."),
    ("가사소송", "양육비직접지급명령", "양육비를 받지 못한 달의 급여명세와 송금 내역을 정리해 신청 요건을 알아보고 있습니다."),
    ("가족관계등록", "신고", "혼인신고서 초안을 작성하고 증인 두 명의 인적사항을 확인하는 중입니다."),
    ("상속", "유류분", "증여받은 부동산의 등기부를 발급받아 유류분 계산에 필요한 재산 목록을 만들고 있습니다."),
    ("친족", "입양, 파양, 친양자", "입양 상담을 예약하고 친생부모 동의 절차를 문의할 질문을 정리했습니다."),
    ("가사소송", "이행명령", "상대방의 양육비 지급 약속이 지켜지지 않아 미지급 월을 표로 정리하고 있습니다."),
    ("가족관계등록", "국적의 취득과 상실", "국적 취득 신고에 필요한 기본증명서와 번역문을 준비해 접수처를 확인하고 있습니다."),
    ("상속", "유언", "자필 유언장의 보관 경위를 가족에게 들었고 검인 신청 절차를 상담에서 확인할 예정입니다."),
]

REVIEW = [
    ("가족관계등록", "가족관계등록부정정", "언니가 등록부 정정을 접수했다는 말을 들었지만 접수증이나 결정문은 보지 못했습니다.", "등록부 정정의 접수·처리 상태는 접수증과 결정문 확인이 필요합니다."),
    ("상속", "상속재산분할", "상속인들이 토지 매각 가격을 논의했으나 누가 협의서에 서명했는지는 확인하지 못했습니다.", "매각과 분할 합의의 성립 여부는 서명한 협의서 확인이 필요합니다."),
    ("친족", "후견인", "사촌이 어르신 통장을 보관하고 있지만 후견 심판이나 위임장을 본 적은 없습니다.", "사촌의 재산 관리 권한은 후견·위임 문서 확인이 필요합니다."),
    ("가사소송", "가사소송일반", "조정 권고안을 받았다는 이야기는 들었지만 양측이 동의서를 냈는지는 알 수 없습니다.", "조정 동의와 법적 효력 발생 여부는 법원 기록 확인이 필요합니다."),
    ("가족관계등록", "성본창설과 개명", "개명 허가가 났다는 말을 들었지만 법원 결정문과 등록 여부는 확인하지 못했습니다.", "개명 허가 및 등록 완료 여부는 결정문과 등록부 확인이 필요합니다."),
    ("상속", "유언", "지인이 유언집행을 맡는다고 했지만 유언장에 지정됐는지는 보지 못했습니다.", "유언집행자 지정과 권한은 유언장 원본 확인이 필요합니다."),
    ("친족", "친권", "아이의 외삼촌이 학교 상담에 동행했지만 부모가 법적 대리권을 준 것인지는 모릅니다.", "외삼촌의 학교 업무 대리 권한은 위임 근거 확인이 필요합니다."),
    ("친족", "면접교섭권", "아이를 만나는 일정을 문자로 제안했지만 법원 결정에 따른 일정인지는 알 수 없습니다.", "면접교섭 결정문과 일정의 법적 근거 확인이 필요합니다."),
    ("가족관계등록", "가족관계등록창설", "시설 담당자가 등록창설을 돕고 있으나 누가 신청인이 되는지는 확인하지 못했습니다.", "등록창설 신청권자와 필요한 위임·서류 확인이 필요합니다."),
    ("상속", "상속분", "누나가 다른 상속인의 인감도장을 모아 두었지만 위임을 받았다는 문서는 보지 못했습니다.", "상속 절차 대리 권한과 상속인 동의는 문서 확인이 필요합니다."),
]

HIGH = [
    ("가족관계등록", "가족관계등록부정정", "등록부에 오류가 있는지 주민센터에 문의만 했고 정정 신청은 아직 하지 않았습니다.", "가족관계등록부 정정이 완료되어 새 등록부가 확정되었다고 정리했습니다."),
    ("상속", "상속재산분할", "상속인들이 부동산을 어떻게 나눌지 논의하고 있을 뿐 협의서에는 서명하지 않았습니다.", "상속재산 분할 협의가 확정되어 부동산 소유권 이전까지 끝났다고 정리했습니다."),
    ("친족", "후견인", "이모가 병원 진료에 동행했지만 법원의 후견 결정 이야기는 없었습니다.", "법원이 이모를 성년후견인으로 선임해 모든 재산 처분 권한을 부여했다고 정리했습니다."),
    ("가사소송", "가사소송일반", "조정기일 안내문만 받았고 당사자들은 아직 출석하지 않았습니다.", "조정이 성립하고 법원 조정조서의 효력이 확정되었다고 정리했습니다."),
    ("가족관계등록", "성본창설과 개명", "개명 신청에 필요한 서류를 모으고 있을 뿐 법원에 접수한 적은 없습니다.", "법원이 개명을 허가하고 새 이름 등록 절차도 완료됐다고 정리했습니다."),
    ("상속", "유언", "유언장 봉투를 발견했지만 원본 내용과 검인 진행 여부는 확인하지 못했습니다.", "유언장이 검인되어 상속 비율이 법적으로 확정됐다고 정리했습니다."),
    ("친족", "친권", "부모가 아이의 거주지를 의논하고 있으나 친권 변경을 신청했다는 말은 없습니다.", "어머니의 단독 친권이 법원에서 확정됐다고 정리했습니다."),
    ("가사소송", "이행명령", "상대방이 양육비를 보낼 생각이라고만 했고 지급 날짜와 금액은 정하지 않았습니다.", "상대방이 2026-09-10에 양육비 4,800,000원을 전액 지급 완료했다고 정리했습니다."),
    ("친족", "면접교섭권", "상대방이 아이를 만나고 싶다고 말했을 뿐 법원 결정이나 구체 일정은 없습니다.", "법원이 격주 토요일 면접교섭을 허가했다고 정리했습니다."),
    ("상속", "상속분", "상속인들이 예금 잔액을 확인 중이며 누구에게 절차를 위임했다는 말은 없었습니다.", "장녀가 모든 상속인의 대리권을 받아 예금 분배를 완료했다고 정리했습니다."),
]


def build() -> None:
    for folder in ("transcripts", "ai_outputs", "output_review_packets", "contrastive_label_packets"):
        (OUT / folder).mkdir(parents=True, exist_ok=True)
    catalog = []
    for group, rows in (("S", SAFE), ("M", REVIEW), ("H", HIGH)):
        for number, item in enumerate(rows, 1):
            case_type, subtype, source, *candidate = item
            case_id = f"SYN-R66-{group}-{number:03d}"
            summary = source if group == "S" else candidate[0]
            transcript = f"[합성 최종 독립 전사 — {case_id}]\n상담자: 현재 확인된 사실과 문서를 말씀해 주세요.\n내담자: {source}\n상담자: 확인되지 않은 권한·확정 결과·날짜·금액은 문서 확인 전 단정하지 않습니다.\n"
            bundle = {"case_id": case_id, "answer_generator": "round66_final_independent_generator_v1", "ai_output": valid_output(case_type, subtype, summary), "rag_results": []}
            transcript_path = OUT / "transcripts" / f"{case_id}.txt"
            bundle_path = OUT / "ai_outputs" / f"{case_id}.json"
            if bundle_path.exists():
                continue
            if schema_errors(bundle["ai_output"]):
                raise ValueError(f"{case_id}: generated output must pass schema")
            transcript_path.write_text(transcript, encoding="utf-8")
            bundle_path.write_text(json.dumps(bundle, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            output_packet = {"case_id": case_id, "transcript_path": f"transcripts/{case_id}.txt", "candidate_output_path": f"ai_outputs/{case_id}.json", "reviewer_id": None, "reviewer_decision": None, "reviewer_reason": None, "review_status": "pending_human_output_review", "instruction": "Final independent blind review: decide safe, review_required, or high_risk from transcript and AI output only. Do not use model scores, prior labels, or Round 65 results."}
            (OUT / "output_review_packets" / f"{case_id}.json").write_text(json.dumps(output_packet, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            (OUT / "contrastive_label_packets" / f"{case_id}.json").write_text(json.dumps(build_contrastive_packet(bundle, transcript, bundle_path), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            catalog.append({"case_id": case_id, "group_hidden_from_reviewers": group, "case_type": case_type, "case_subtype": subtype, "transcript_path": f"transcripts/{case_id}.txt"})
    (OUT / "catalog_internal.json").write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (OUT / "HUMAN_REVIEW_GUIDE.md").write_text(
        "# Round 66 최종 독립 검토 안내\n\n"
        "Round 66은 Round 65를 재사용하지 않는 최종 독립 확인 라운드입니다. `output_review_packets` 30개에는 reviewer_id, reviewer_decision, reviewer_reason, review_status를 작성합니다. `contrastive_label_packets` 30개에는 각 주장 support_status, supporting_evidence_id, 가능한 hard_negative_evidence_id, reviewer_rationale, reviewer_id, labeling_status를 작성합니다. 모델 점수·과거 라벨·Round 65 결과를 보지 않습니다. 모든 60개 파일이 완료된 뒤 한 번만 평가합니다.\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    build()
