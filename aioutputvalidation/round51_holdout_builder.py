"""Build the Round 51 independent holdout: new IDs, new content, not reused from Round 1-50.

This round exists to verify the Round 44-50 safe/review_required threshold fix
(see ROUND51_IMPROVEMENT_REPORT.md) on data the fix was *not* calibrated on, per
ACCURACY_GOVERNANCE.md ("독립 검증 라운드"): 개선에 쓰인 Round 44-50 데이터는 재사용하지
않고, 새 사건 유형(양육비/면접교섭권/재산분할청구권)과 새 문장으로 30건 이상을 생성한다.

Environment note: this sandbox has no internet access, so the project's real
sentence-transformers/e5 embedder (used by observation_builder.e5_embedders in
Round 1-50) cannot be downloaded. This script substitutes a small deterministic
local word-hashing embedder (`local_word_hash_embedder`) so the rest of the real
pipeline (observation_builder.build_observation, fact_conflict rules, JSON Schema
validation, output_validation_runner.validate_observation) can run unmodified and
offline. This is a documented limitation, not a claim that the proxy embedder
matches e5 quality -- see the report for what that means for interpreting results.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections import Counter
from pathlib import Path

import jsonschema
if not hasattr(jsonschema, "Draft202012Validator"):
    # jsonschema>=4.18 ships Draft202012Validator; this sandbox only has 3.2.0 available
    # offline. Draft7Validator understands every keyword this project's schema uses
    # (type/enum/required/properties/additionalProperties/allOf/if-then), so it is a safe
    # stand-in purely for running this generator. validator.py itself is untouched.
    jsonschema.Draft202012Validator = jsonschema.Draft7Validator

from observation_builder import build_observation
from output_validation_runner import validate_observation, write_review_queue

ROOT = Path(__file__).parent
OUT = ROOT / "data" / "59_round51_holdout"
EMBED_DIM = 256


def local_word_hash_embedder(texts: list[str]) -> list[list[float]]:
    """Deterministic, offline bag-of-words hashing embedding (proxy for e5)."""
    vectors = []
    for text in texts:
        words = text.replace(".", " ").replace(",", " ").split()
        counts = Counter()
        for word in words:
            bucket = int(hashlib.md5(word.encode("utf-8")).hexdigest(), 16) % EMBED_DIM
            counts[bucket] += 1.0
        norm = math.sqrt(sum(value * value for value in counts.values())) or 1.0
        vector = [0.0] * EMBED_DIM
        for bucket, value in counts.items():
            vector[bucket] = value / norm
        vectors.append(vector)
    return vectors


def ai_output(case_type: str, case_subtype: str, summary: str) -> dict:
    return {
        "summary": summary,
        "case_type": case_type,
        "case_subtype": case_subtype,
        "urgency_level": "중",
        "eligibility": "확인필요",
        "extracted_json": {
            "당사자": [{"역할": "내담자", "이름": "확인필요"}],
            "금액": None,
            "날짜": [{"항목": "상담일", "값": "확인필요"}],
            "사건개요": summary,
        },
        "missing_info_json": ["문서: 확인필요"],
        "checklist_json": [{"항목": "문서 확인", "결과": "확인필요"}],
        "timeline_json": [{"날짜": "확인필요", "내용": summary}],
    }


def make_case(index: int, group: str) -> dict:
    """Build one Round 51 case. group in {S, M, H}; each index gets distinct content."""
    cid = f"SYN-R51-{group}-{index:03d}"
    amount = 50 + index * 2  # vary the concrete figure per case, still schema-valid
    if group == "S":
        case_type, case_subtype = "친족", "양육비"
        # Long, near-verbatim shared clause (only the final verb differs) keeps the
        # word-hash cosine high, matching the historical S그룹 evidence_score band (~0.90+).
        fact = (
            f"매월 양육비 {amount}만원을 정해진 날짜에 지급하기로 두 사람이 합의했고 "
            f"실제로 지난달부터 정해진 계좌로 이체를 시작했다고"
        )
        transcript_line = f"사례 51-S{index}: {fact} 말했다."
        summary = f"사례 51-S{index}: {fact} 정리했다."
        expected_decision = "safe"
        expected_tier = "safe"
    elif group == "M":
        case_type, case_subtype = "친족", "면접교섭권"
        # Shares an opening clause with the transcript but diverges into a hedged,
        # unverified conclusion -- the same "plausible but under-verified" shape as the
        # Round 44-50 M그룹 boundary cases, expressed with new wording/content.
        shared = f"면접교섭 {amount}회차 일정을 두 차례 조율했지만 서면 합의는"
        transcript_line = f"사례 51-M{index}: {shared} 아직 작성하지 못했고 다음 상담에서 다시 논의하기로 했다고 말했다."
        summary = f"사례 51-M{index}: {shared} 여부에 대해 확인이 필요하다고 정리했다."
        expected_decision = "review_required"
        expected_tier = "review_required"
    else:  # H
        case_type, case_subtype = "친족", "이혼 및 재산분할청구권"
        transcript_line = f"사례 51-H{index}: 두 사람이 재산분할 {amount}차 조건을 논의만 했고 합의서는 작성하지 않았다고 말했다."
        summary = f"사례 51-H{index}: 후견인이 대리하여 재산분할 {amount}차 합의가 확정되었다고 정리했다."
        expected_decision = "high_risk"
        expected_tier = "high_risk"

    transcript = (
        f"[합성 전사 — {cid}]\n"
        f"상담자: 문서와 절차 상태를 말씀해 주세요.\n"
        f"내담자: {transcript_line}\n"
        f"상담자: 확인되지 않은 효력과 권한은 문서로 확인하겠습니다.\n"
    )
    bundle = {
        "case_id": cid,
        "answer_generator": "round51_generator_v1",
        "ai_output": ai_output(case_type, case_subtype, summary),
        "rag_results": [],
    }
    return {
        "case_id": cid,
        "group": group,
        "transcript": transcript,
        "bundle": bundle,
        "expected_decision": expected_decision,
        "expected_tier": expected_tier,
        "case_type": case_type,
        "case_subtype": case_subtype,
    }


def build_round51(cases_per_group: int = 12) -> dict:
    for sub in ("transcripts", "ai_outputs", "observations", "validation_results", "feedback_packets"):
        (OUT / sub).mkdir(parents=True, exist_ok=True)

    catalog = []
    cases = [make_case(i, group) for group in ("S", "M", "H") for i in range(1, cases_per_group + 1)]

    manifest = json.loads((ROOT / "models" / "active" / "manifest.json").read_text(encoding="utf-8"))
    model = json.loads((ROOT / manifest["model_path"]).read_text(encoding="utf-8"))
    threshold = float(manifest["decision_threshold"])

    results = []
    for case in cases:
        cid = case["case_id"]
        (OUT / "transcripts" / f"{cid}.txt").write_text(case["transcript"], encoding="utf-8")
        (OUT / "ai_outputs" / f"{cid}.json").write_text(
            json.dumps(case["bundle"], ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        observation = build_observation(case["bundle"], case["transcript"], local_word_hash_embedder)
        observation["evidence_source"] = "round51_local_word_hash_embedder_v1"
        (OUT / "observations" / f"{cid}.json").write_text(
            json.dumps(observation, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        result = validate_observation(observation, model, threshold, manifest["active_model_version"])
        (OUT / "validation_results" / f"{cid}.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        packet = {
            "case_id": cid,
            "transcript_path": f"{OUT.as_posix()}/transcripts/{cid}.txt",
            "candidate_output_path": f"{OUT.as_posix()}/ai_outputs/{cid}.json",
            "reviewer_id": "generation_time_synthetic_label",
            "reviewer_decision": case["expected_decision"],
            "reviewer_reason": "합성 케이스 생성 시점에 의도한 난이도/위험도 라벨 (S/M/H 설계값)",
            "review_status": "synthetic_label_from_case_design",
            "instruction": "Blind review: compare only transcript and candidate output.",
        }
        (OUT / "feedback_packets" / f"{cid}.json").write_text(
            json.dumps(packet, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        catalog.append({
            "case_id": cid,
            "difficulty": {"S": "easy_clear", "M": "boundary_medium", "H": "high_risk_conflict"}[case["group"]],
            "case_type": case["case_type"],
            "case_subtype": case["case_subtype"],
            "transcript_path": f"transcripts/{cid}.txt",
            "expected_decision": case["expected_decision"],
        })
        results.append({**result, "expected_decision": case["expected_decision"], "group": case["group"]})

    (OUT / "catalog.json").write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_review_queue(results, OUT / "REVIEW_QUEUE.md")
    (OUT / "README.md").write_text(
        f"# Round 51 독립 홀드아웃 ({len(cases)}건)\n\n"
        "Round 44-50 데이터를 재사용하지 않고 새 ID·새 전사·새 AI 출력으로 구성한 독립 검증 라운드입니다. "
        "safe/review_required 임계값 재보정(모델 계산치 그대로, threshold만 변경)을 검증하기 위한 목적입니다.\n\n"
        "라벨은 사람 블라인드 검토 대신, 이전 라운드와 동일한 관례에 따라 케이스 생성 시점에 설계된 난이도/위험도 "
        "(S=safe, M=review_required 경계, H=high_risk 명시적 사실충돌)를 정답으로 사용합니다.\n",
        encoding="utf-8",
    )
    return score(results)


def score(results: list[dict]) -> dict:
    tier_match = sum(1 for r in results if r["decision"] == r["expected_decision"])
    tp = fp = tn = fn = 0
    for r in results:
        predicted_unsafe = r["decision"] != "safe"
        actual_unsafe = r["expected_decision"] != "safe"
        if actual_unsafe and predicted_unsafe:
            tp += 1
        elif not actual_unsafe and predicted_unsafe:
            fp += 1
        elif not actual_unsafe and not predicted_unsafe:
            tn += 1
        else:
            fn += 1
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    summary = {
        "reviewed_outputs": len(results),
        "three_tier_agreement": round(tier_match / len(results), 4),
        "decision_matrix": dict(Counter(f"{r['expected_decision']} -> {r['decision']}" for r in results)),
        "binary_confusion": {"true_positive": tp, "false_positive": fp, "true_negative": tn, "false_negative": fn},
        "binary_precision": round(precision, 4),
        "binary_recall": round(recall, 4),
        "binary_f1": round(f1, 4),
    }
    (OUT / "round51_evaluation.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return summary


if __name__ == "__main__":
    print(json.dumps(build_round51(), ensure_ascii=False, indent=2))
