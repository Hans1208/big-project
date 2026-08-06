"""Freeze Round 20 final-holdout agreement and binary safety metrics."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path("data/28_round20_final_holdout")


def main() -> None:
    packets = [json.loads(path.read_text(encoding="utf-8")) for path in sorted((ROOT / "feedback_packets").glob("SYN-R20-*.json"))]
    if len(packets) != 30 or any(packet.get("review_status") != "completed_human_output_review" for packet in packets):
        raise ValueError("Round 20 requires 30 completed human reviews")
    matrix: dict[str, int] = {}
    matches = tp = fp = tn = fn = 0
    for packet in packets:
        model = json.loads((ROOT / "validation_results" / f"{packet['case_id']}.json").read_text(encoding="utf-8"))["decision"]
        human = packet["reviewer_decision"]
        if human not in {"safe", "review_required", "high_risk"}:
            raise ValueError(f"invalid human decision: {packet['case_id']}")
        matrix[f"{model} -> {human}"] = matrix.get(f"{model} -> {human}", 0) + 1
        matches += int(model == human)
        predicted_non_safe, human_non_safe = model != "safe", human != "safe"
        if predicted_non_safe and human_non_safe: tp += 1
        elif predicted_non_safe: fp += 1
        elif human_non_safe: fn += 1
        else: tn += 1
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    report = {
        "round": "Round 20 final operational holdout",
        "reviewed_outputs": len(packets),
        "exact_decision_agreement": round(matches / len(packets), 4),
        "decision_matrix": matrix,
        "binary_non_safe_metrics": {"true_positive": tp, "false_positive": fp, "true_negative": tn, "false_negative": fn, "accuracy": round((tp + tn) / len(packets), 4), "precision": round(precision, 4), "recall": round(recall, 4), "f1": round(2 * precision * recall / (precision + recall), 4) if precision + recall else 0.0},
        "final_holdout_rule": "Results are frozen and must not be used to recalibrate rules, thresholds, or MLP weights.",
    }
    (ROOT / "final_operational_evaluation.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
