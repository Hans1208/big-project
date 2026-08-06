"""Evaluate completed Round 65 independent human reviews without changing active models."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from contrastive_evaluation import evaluate_packets
from observation_builder import build_observation, e5_embedders
from output_review_feedback import feedback_agreement
from output_validation_runner import load_runtime_manifest, validate_observation, write_review_queue


ROOT = Path(__file__).parent
OUT = ROOT / "data" / "65_round65_independent_holdout"


def binary_metrics(results: list[dict], packets: list[dict]) -> dict:
    decisions = {packet["case_id"]: packet["reviewer_decision"] for packet in packets}
    tp = fp = tn = fn = 0
    for result in results:
        predicted_unsafe = result["decision"] != "safe"
        actual_unsafe = decisions[result["case_id"]] != "safe"
        if predicted_unsafe and actual_unsafe:
            tp += 1
        elif predicted_unsafe:
            fp += 1
        elif actual_unsafe:
            fn += 1
        else:
            tn += 1
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "binary_confusion": {"true_positive": tp, "false_positive": fp, "true_negative": tn, "false_negative": fn},
        "binary_precision": round(precision, 4),
        "binary_recall": round(recall, 4),
        "binary_f1": round(f1, 4),
    }


def evaluate() -> dict:
    output_packets = [json.loads(path.read_text(encoding="utf-8")) for path in sorted((OUT / "output_review_packets").glob("SYN-*.json"))]
    incomplete = [packet["case_id"] for packet in output_packets if packet.get("review_status") != "completed_human_output_review"]
    if incomplete:
        raise ValueError("incomplete output reviews: " + ", ".join(incomplete))

    manifest = load_runtime_manifest(ROOT / "models" / "active" / "manifest.json")
    model = json.loads((ROOT / manifest["model_path"]).read_text(encoding="utf-8"))
    claim_embedder, evidence_embedder = e5_embedders("intfloat/multilingual-e5-small")
    results_dir = OUT / "validation_results"
    observations_dir = OUT / "observations"
    results_dir.mkdir(exist_ok=True)
    observations_dir.mkdir(exist_ok=True)
    results = []
    for bundle_path in sorted((OUT / "ai_outputs").glob("SYN-*.json")):
        bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
        transcript = (OUT / "transcripts" / f"{bundle['case_id']}.txt").read_text(encoding="utf-8")
        observation = build_observation(bundle, transcript, claim_embedder, evidence_embedder)
        result = validate_observation(observation, model, float(manifest["decision_threshold"]), manifest["active_model_version"])
        (observations_dir / bundle_path.name).write_text(json.dumps(observation, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (results_dir / bundle_path.name).write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        results.append(result)
    summary = {"validated_outputs": len(results), "decision_counts": dict(Counter(result["decision"] for result in results)), "model_version": manifest["active_model_version"], "mode": "shadow_evaluation"}
    (results_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_review_queue(results, results_dir / "REVIEW_QUEUE.md")

    output_report = feedback_agreement(results_dir, OUT / "output_review_packets")
    output_report.update(binary_metrics(results, output_packets))
    contrastive_packets = [json.loads(path.read_text(encoding="utf-8")) for path in sorted((OUT / "contrastive_label_packets").glob("SYN-*.json"))]
    contrastive_report = evaluate_packets(contrastive_packets, claim_embedder, evidence_embedder)
    contrastive_report.update({"embedding_model": "intfloat/multilingual-e5-small", "label_source": "independent_human_contrastive_review"})
    report = {"round": 65, "scope": "independent_holdout_after_round64_calibration", "output_validation": output_report, "contrastive": contrastive_report}
    (OUT / "round65_output_evaluation.json").write_text(json.dumps(output_report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (OUT / "round65_contrastive_evaluation.json").write_text(json.dumps(contrastive_report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (OUT / "round65_independent_evaluation.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


if __name__ == "__main__":
    print(json.dumps(evaluate(), ensure_ascii=False, indent=2))
