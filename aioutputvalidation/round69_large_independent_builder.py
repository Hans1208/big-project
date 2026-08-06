"""Build a frozen 90-case (30 per tier) blinded scale-up confirmation set."""

import json
from pathlib import Path

from contrastive_label_packet import build_contrastive_packet
from round63_independent_holdout_builder import valid_output
from round68_tier_independent_builder import HIGH, REVIEW, SAFE
from validator import schema_errors


ROOT = Path(__file__).parent
OUT = ROOT / "data" / "69_round69_large_independent"

# These additions vary wording and surrounding facts without changing the
# reviewer-facing risk tier.  No model output or prior round label is exposed.
CONTEXTS = (
    "관련 자료는 아직 정리 중이며 확정되지 않은 내용은 문서로 다시 확인할 예정입니다.",
    "상담 기록에는 이 사실 외의 법원 결정·위임장·접수증 정보가 포함되어 있지 않습니다.",
    "가족 또는 담당 기관에 추가 서류를 문의할 계획이지만 현재 확인된 범위만 말한 것입니다.",
)


def _expanded(rows):
    return [(*row[:-1], f"{row[-1]} {context}") for row in rows for context in CONTEXTS]


def build() -> None:
    if OUT.exists() and any(OUT.iterdir()):
        raise RuntimeError(f"Refusing to overwrite independent holdout: {OUT}")
    for folder in ("transcripts", "ai_outputs", "output_review_packets", "contrastive_label_packets"):
        (OUT / folder).mkdir(parents=True, exist_ok=True)

    # R68 source cases are expanded only before review; the 90 packets remain
    # blind to reviewers and no R68 decision/result is copied into them.
    for group, rows in (("S", _expanded(SAFE)), ("M", _expanded(REVIEW)), ("H", _expanded(HIGH))):
        for number, item in enumerate(rows, 1):
            case_type, subtype, source, *candidate = item
            case_id = f"SYN-R69-{group}-{number:03d}"
            summary = source if group == "S" else candidate[0]
            transcript = (
                f"[합성 독립 전사 — {case_id}]\n"
                "상담자: 현재 확인된 사실과 문서를 말씀해 주세요.\n"
                f"내담자: {source}\n"
                "상담자: 확인되지 않은 권한·확정 결과·날짜·금액은 문서 확인 전 단정하지 않습니다.\n"
            )
            bundle = {
                "case_id": case_id,
                "answer_generator": "round69_large_independent_generator_v1",
                "ai_output": valid_output(case_type, subtype, summary),
                "rag_results": [],
            }
            if schema_errors(bundle["ai_output"]):
                raise ValueError(f"{case_id}: generated output must pass schema")
            bundle_path = OUT / "ai_outputs" / f"{case_id}.json"
            (OUT / "transcripts" / f"{case_id}.txt").write_text(transcript, encoding="utf-8")
            bundle_path.write_text(json.dumps(bundle, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            packet = {
                "case_id": case_id,
                "transcript_path": f"transcripts/{case_id}.txt",
                "candidate_output_path": f"ai_outputs/{case_id}.json",
                "reviewer_id": None,
                "reviewer_decision": None,
                "reviewer_reason": None,
                "review_status": "pending_human_output_review",
                "instruction": "Independent blind review: decide safe, review_required, or high_risk from transcript and AI output only. Do not use prior-round labels or model decisions.",
            }
            (OUT / "output_review_packets" / f"{case_id}.json").write_text(json.dumps(packet, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            (OUT / "contrastive_label_packets" / f"{case_id}.json").write_text(
                json.dumps(build_contrastive_packet(bundle, transcript, bundle_path), ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
    (OUT / "HUMAN_REVIEW_GUIDE.md").write_text(
        "# Round 69 대규모 블라인드 검토 안내\n\n"
        "Round 69는 각 위험 단계 30건, 총 90건의 규모 확인용 블라인드 배치다. Round 68 위험 유형을 문맥·표현으로 확장했으므로 완전히 새로운 유형만의 독립 일반화 시험은 아니다. 출력 검토와 contrastive 근거 검토를 각각 90개 완료한다. "
        "모델 점수·이전 라운드 라벨·예상 판정은 보지 않는다. 이 라운드는 모델·임계값을 바꾸지 않은 상태에서 현재 수치를 다시 측정한다.\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    build()
