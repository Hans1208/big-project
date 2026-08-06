"""Prepare blind human feedback packets for outputs flagged by the validator."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path


def build_feedback_packet(result: dict) -> dict:
    round_root = "data/24_round16_improvement" if result["case_id"].startswith("SYN-R16-") else "data/23_round15_holdout" if result["case_id"].startswith("SYN-R15-") else "data"
    is_round_batch = round_root != "data"
    source_root = round_root
    transcript_dir = "transcripts" if is_round_batch else "02_transcripts"
    output_dir = "ai_outputs" if is_round_batch else "03_ai_outputs/generated"
    return {
        "case_id": result["case_id"],
        "transcript_path": f"{source_root}/{transcript_dir}/{result['case_id']}.txt",
        "candidate_output_path": f"{source_root}/{output_dir}/{result['case_id']}.json",
        "reviewer_id": None,
        "reviewer_decision": None,
        "reviewer_reason": None,
        "review_status": "pending_human_output_review",
        "instruction": "Review the transcript and candidate output independently. The validator decision is intentionally hidden until comparison.",
    }


def feedback_agreement(results_dir: Path, feedback_dir: Path) -> dict:
    packets = [json.loads(path.read_text(encoding="utf-8")) for path in sorted(feedback_dir.glob("SYN-*.json"))]
    completed_statuses = {"completed_human_output_review", "reviewed"}
    incomplete = [packet["case_id"] for packet in packets if packet.get("review_status") not in completed_statuses or packet.get("reviewer_decision") not in {"safe", "review_required", "high_risk"}]
    if incomplete:
        raise ValueError("incomplete human output reviews: " + ", ".join(incomplete))
    matches = 0
    matrix = Counter()
    for packet in packets:
        result = json.loads((results_dir / f"{packet['case_id']}.json").read_text(encoding="utf-8"))
        matches += int(packet["reviewer_decision"] == result["decision"])
        matrix[f"{result['decision']} -> {packet['reviewer_decision']}"] += 1
    return {"reviewed_outputs": len(packets), "exact_decision_agreement": round(matches / len(packets), 4), "decision_matrix": dict(matrix)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Prepare or compare blind human feedback for flagged output validation results.")
    parser.add_argument("action", choices=("prepare", "evaluate"))
    parser.add_argument("--results-dir", type=Path, default=Path("data/07_validation_results"))
    parser.add_argument("--feedback-dir", type=Path, default=Path("data/08_output_review_feedback/packets"))
    parser.add_argument("--output", type=Path, default=Path("data/metrics/output_review_agreement.json"))
    parser.add_argument("--decisions", nargs="+", choices=("safe", "review_required", "high_risk"), default=("review_required", "high_risk"), help="Model decisions to include when preparing a blind review batch.")
    args = parser.parse_args()
    if args.action == "prepare":
        args.feedback_dir.mkdir(parents=True, exist_ok=True)
        results = [json.loads(path.read_text(encoding="utf-8")) for path in sorted(args.results_dir.glob("SYN-*.json"))]
        selected = [result for result in results if result["decision"] in args.decisions]
        for result in selected:
            path = args.feedback_dir / f"{result['case_id']}.json"
            if not path.exists():
                path.write_text(json.dumps(build_feedback_packet(result), ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Prepared {len(selected)} blind output-review packets")
    else:
        report = feedback_agreement(args.results_dir, args.feedback_dir)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(report, ensure_ascii=False, indent=2))
