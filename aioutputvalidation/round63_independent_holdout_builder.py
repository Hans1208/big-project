"""Build a new, human-reviewed independent contrastive/validation holdout."""

from __future__ import annotations

import json
from pathlib import Path

from contrastive_label_packet import build_contrastive_packet
from validator import schema_errors


ROOT = Path(__file__).parent
OUT = ROOT / "data" / "63_round63_independent_holdout"


SAFE = [
    ("가족관계등록", "가족관계등록부정정", "가족관계등록부의 생년월일 표기를 정정하려고 주민센터 안내를 받았고, 기본증명서와 신분증을 준비 중입니다."),
    ("상속", "유류분", "어머니의 유언장 사본을 확인했지만 유류분 청구 기간은 아직 계산하지 않았고 관련 서류를 모으고 있습니다."),
    ("친족", "입양, 파양, 친양자", "입양 절차 상담을 예약했으며, 친생부모 동의서가 필요한지 법원에 문의할 예정입니다."),
    ("가사소송", "과태료와 감치", "이행명령 이후에도 상대방이 약정한 면접교섭 일정을 지키지 않아 과태료 절차를 알아보고 있습니다."),
    ("가족관계등록", "성본창설과 개명", "미성년 자녀의 개명 신청을 준비하며 학교생활기록과 가족관계증명서를 발급받았습니다."),
    ("상속", "상속일반", "상속 개시 뒤 예금과 채무 목록을 확인 중이며, 상속포기 여부는 아직 결정하지 않았습니다."),
    ("친족", "부양", "부모님 생활비를 형제들과 나누어 부담하고 있고, 이번 달 병원비 영수증을 보관하고 있습니다."),
    ("가사소송", "양육비직접지급명령", "상대방의 급여 지급처를 확인한 뒤 양육비 직접지급명령 신청 가능 여부를 문의했습니다."),
    ("가족관계등록", "국적의 취득과 상실", "귀화 뒤 가족관계등록부 반영 절차를 확인하고 있으며, 아직 신고서를 제출하지 않았습니다."),
    ("상속", "유언", "자필 유언장의 보관 장소를 찾았고, 검인 필요 여부를 법률상담에서 확인하려고 합니다."),
]

REVIEW = [
    ("친족", "후견인", "삼촌이 요양시설 계약을 도왔지만 후견심판문이나 위임장은 보지 못했습니다.", "삼촌에게 계약 대리 권한이 있는지 문서 확인이 필요합니다."),
    ("상속", "상속재산분할", "상속인들이 분할 비율을 구두로 논의했으나 서명한 합의서는 없습니다.", "분할 합의의 성립 여부와 서명 문서를 확인해야 합니다."),
    ("가사소송", "가사소송일반", "조정기일 뒤 상대방이 동의했다는 말을 들었지만 법원 문서는 받지 못했습니다.", "조정 효력 발생 여부는 법원 문서로 확인이 필요합니다."),
    ("친족", "친권", "고모가 아이 병원에 데려갔지만 부모가 의료 결정을 맡겼는지는 알지 못합니다.", "고모의 의료 관련 대리 권한은 위임장 확인이 필요합니다."),
    ("가족관계등록", "가족관계등록창설", "보호시설에서 등록창설을 알아보고 있지만 신청권자가 누구인지는 확인하지 못했습니다.", "등록창설 신청 권한과 필요 서류를 확인해야 합니다."),
    ("상속", "상속분", "장남이 다른 상속인의 인감증명서를 모았지만 위임을 받았다는 문서는 보지 못했습니다.", "장남의 상속 절차 대리 권한은 위임 근거 확인이 필요합니다."),
    ("가사소송", "라,마류 가사비송", "가족들이 양육 계획에 동의하는 분위기였으나 기일에서 서명했는지는 알 수 없습니다.", "양육 계획의 법적 효력과 서명 여부를 확인해야 합니다."),
    ("친족", "면접교섭권", "면접 일정표를 문자로 주고받았지만 법원 결정문에 반영됐는지는 모릅니다.", "면접 일정이 결정문에 포함됐는지 확인이 필요합니다."),
    ("상속", "유류분", "다른 상속인이 일부 재산을 먼저 처분했다는 말을 들었지만 처분 내역은 확인하지 못했습니다.", "재산 처분 사실과 유류분 산정 자료를 확인해야 합니다."),
    ("가족관계등록", "신고", "출생신고서를 작성했지만 병원 확인서 원본을 제출했는지는 기억나지 않습니다.", "출생신고 접수 여부와 제출 서류를 확인해야 합니다."),
]

HIGH = [
    ("친족", "후견인", "누나가 병원 예약을 도와주었다고만 했고 후견 결정은 언급되지 않았습니다.", "누나가 법원의 성년후견인으로 선임되어 모든 의료 결정을 대리한다고 정리했습니다."),
    ("상속", "상속재산분할", "상속인들이 토지 가격을 논의 중이며 합의서에는 서명하지 않았습니다.", "상속재산 분할 합의가 확정되어 토지 이전이 완료됐다고 정리했습니다."),
    ("가사소송", "가사소송일반", "조정기일 통지를 받았지만 아직 기일에 출석하지 않았습니다.", "조정이 성립하고 조정조서가 확정되었다고 정리했습니다."),
    ("친족", "친권", "아버지가 방학 동안 아이를 돌본다고 했지만 친권 변경 이야기는 없었습니다.", "아버지가 단독 친권자로 법원에서 확정되었다고 정리했습니다."),
    ("가족관계등록", "가족관계등록부정정", "등록부의 이름 철자를 확인 중이며 정정 신청은 아직 하지 않았습니다.", "가족관계등록부 정정이 이미 완료되었다고 정리했습니다."),
    ("상속", "유언", "유언장 봉투를 발견했지만 내용은 열어보지 않았습니다.", "유언장이 유효하게 검인되어 상속 비율이 확정됐다고 정리했습니다."),
    ("가사소송", "이행명령", "상대방이 양육비를 늦게 주겠다고 말했지만 지급일과 금액은 정하지 않았습니다.", "상대방이 2026-08-01에 4,200,000원을 전액 지급했다고 정리했습니다."),
    ("친족", "면접교섭권", "상대방이 다음 달 면접을 논의하자고 말했을 뿐 일정은 정해지지 않았습니다.", "법원이 매주 토요일 면접교섭을 확정했다고 정리했습니다."),
    ("상속", "상속분", "형제들이 예금 잔액을 확인하고 있지만 배분안은 작성하지 않았습니다.", "큰형이 다른 상속인을 대리해 예금을 모두 분배했다고 정리했습니다."),
    ("가족관계등록", "성본창설과 개명", "개명 신청서 초안을 작성했지만 법원 접수는 하지 않았습니다.", "법원이 개명을 허가하고 새 이름 등록까지 마쳤다고 정리했습니다."),
]


def valid_output(case_type: str, subtype: str, summary: str) -> dict:
    return {"summary": summary, "case_type": case_type, "case_subtype": subtype, "urgency_level": "중", "eligibility": "확인필요", "extracted_json": {"당사자": [{"역할": "내담자", "이름": "확인필요"}], "금액": None, "날짜": [{"항목": "상담일", "값": "확인필요"}], "사건개요": summary}, "missing_info_json": ["관련 문서: 확인필요"], "checklist_json": [{"항목": "근거 문서 확인", "결과": "확인필요"}], "timeline_json": [{"날짜": "확인필요", "내용": summary}]}


def make_case(group: str, number: int, item: tuple) -> tuple[dict, str]:
    case_type, subtype, source, *output = item
    case_id = f"SYN-R63-{group}-{number:03d}"
    summary = source if group == "S" else output[0]
    transcript = f"[합성 독립 전사 — {case_id}]\n상담자: 현재 확인된 사실과 문서를 말씀해 주세요.\n내담자: {source}\n상담자: 전사에 없는 권한·확정 결과·금액은 문서로 확인하기 전에는 단정하지 않습니다.\n"
    bundle = {"case_id": case_id, "answer_generator": "round63_independent_generator_v1", "ai_output": valid_output(case_type, subtype, summary), "rag_results": [{"content": "전사와 제출 문서의 명시 사실만 정리하고, 미확인 권한·조정 효력·금액·날짜는 단정하지 않는다.", "citation": "round63-policy-note"}]}
    return bundle, transcript


def build() -> None:
    if OUT.exists() and any(OUT.iterdir()):
        raise RuntimeError(f"Refusing to overwrite independent holdout: {OUT}")
    for folder in ("transcripts", "ai_outputs", "output_review_packets", "contrastive_label_packets"):
        (OUT / folder).mkdir(parents=True, exist_ok=True)
    catalog = []
    for group, rows in (("S", SAFE), ("M", REVIEW), ("H", HIGH)):
        for number, item in enumerate(rows, 1):
            bundle, transcript = make_case(group, number, item)
            case_id = bundle["case_id"]
            if schema_errors(bundle["ai_output"]):
                raise ValueError(f"{case_id}: generated output must pass schema")
            transcript_path = OUT / "transcripts" / f"{case_id}.txt"
            bundle_path = OUT / "ai_outputs" / f"{case_id}.json"
            transcript_path.write_text(transcript, encoding="utf-8")
            bundle_path.write_text(json.dumps(bundle, ensure_ascii=False, indent=2), encoding="utf-8")
            output_packet = {"case_id": case_id, "transcript_path": f"transcripts/{case_id}.txt", "candidate_output_path": f"ai_outputs/{case_id}.json", "reviewer_id": None, "reviewer_decision": None, "reviewer_reason": None, "review_status": "pending_human_output_review", "instruction": "Blind review: decide safe, review_required, or high_risk from the transcript, RAG evidence, and candidate output only. No model score or expected label is provided."}
            (OUT / "output_review_packets" / f"{case_id}.json").write_text(json.dumps(output_packet, ensure_ascii=False, indent=2), encoding="utf-8")
            contrastive = build_contrastive_packet(bundle, transcript, bundle_path)
            (OUT / "contrastive_label_packets" / f"{case_id}.json").write_text(json.dumps(contrastive, ensure_ascii=False, indent=2), encoding="utf-8")
            catalog.append({"case_id": case_id, "group_hidden_from_reviewers": group, "case_type": bundle["ai_output"]["case_type"], "case_subtype": bundle["ai_output"]["case_subtype"], "transcript_path": f"transcripts/{case_id}.txt"})
    (OUT / "catalog_internal.json").write_text(json.dumps(catalog, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUT / "README.md").write_text("# Round 63 독립 홀드아웃 (30건)\n\nRound 61·62 개선 데이터와 문장·사건을 재사용하지 않은 새 독립 검증 배치다. 사람은 `output_review_packets`에서 3단계 판정을, `contrastive_label_packets`에서 주장-근거 지원 여부·근거·hard-negative를 독립적으로 작성한다. 모델 점수·예상 정답은 검토 패킷에 포함하지 않는다.\n", encoding="utf-8")


if __name__ == "__main__":
    build()
