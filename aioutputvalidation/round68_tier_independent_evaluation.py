"""Evaluate completed Round 68 independent tier-verification reviews."""

import json
from collections import Counter
from pathlib import Path

from contrastive_evaluation import evaluate_packets
from observation_builder import build_observation, e5_embedders
from output_review_feedback import feedback_agreement
from output_validation_runner import load_runtime_manifest, validate_observation, write_review_queue

ROOT = Path(__file__).parent
OUT = ROOT / "data" / "68_round68_tier_independent"


def evaluate():
    packets = [json.loads(p.read_text(encoding="utf-8")) for p in sorted((OUT / "output_review_packets").glob("SYN-*.json"))]
    incomplete = [p["case_id"] for p in packets if p.get("review_status") not in {"completed_human_output_review", "reviewed"} or p.get("reviewer_decision") not in {"safe", "review_required", "high_risk"}]
    if incomplete: raise ValueError("incomplete output reviews: " + ", ".join(incomplete))
    manifest = load_runtime_manifest(ROOT / "models" / "active" / "manifest.json")
    model = json.loads((ROOT / manifest["model_path"]).read_text(encoding="utf-8"))
    embed_claims, embed_evidence = e5_embedders("intfloat/multilingual-e5-small")
    results_dir, observations_dir = OUT / "validation_results", OUT / "observations"
    results_dir.mkdir(exist_ok=True); observations_dir.mkdir(exist_ok=True)
    results = []
    for path in sorted((OUT / "ai_outputs").glob("SYN-*.json")):
        bundle = json.loads(path.read_text(encoding="utf-8"))
        transcript = (OUT / "transcripts" / f"{bundle['case_id']}.txt").read_text(encoding="utf-8")
        observation = build_observation(bundle, transcript, embed_claims, embed_evidence)
        result = validate_observation(observation, model, float(manifest["decision_threshold"]), manifest["active_model_version"])
        (observations_dir / path.name).write_text(json.dumps(observation, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (results_dir / path.name).write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        results.append(result)
    (results_dir / "summary.json").write_text(json.dumps({"validated_outputs": len(results), "decision_counts": dict(Counter(r["decision"] for r in results)), "model_version": manifest["active_model_version"], "mode": "shadow_evaluation"}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_review_queue(results, results_dir / "REVIEW_QUEUE.md")
    output = feedback_agreement(results_dir, OUT / "output_review_packets")
    human = {p["case_id"]: p["reviewer_decision"] for p in packets}; tp = fp = tn = fn = 0
    for result in results:
        predicted, actual = result["decision"] != "safe", human[result["case_id"]] != "safe"
        if predicted and actual: tp += 1
        elif predicted: fp += 1
        elif actual: fn += 1
        else: tn += 1
    precision = tp / (tp + fp) if tp + fp else 0.0; recall = tp / (tp + fn) if tp + fn else 0.0
    output.update({"binary_confusion": {"true_positive": tp, "false_positive": fp, "true_negative": tn, "false_negative": fn}, "binary_precision": round(precision, 4), "binary_recall": round(recall, 4), "binary_f1": round(2 * precision * recall / (precision + recall), 4) if precision + recall else 0.0})
    contrastive_packets = []
    for path in sorted((OUT / "contrastive_label_packets").glob("SYN-*.json")):
        packet = json.loads(path.read_text(encoding="utf-8"))
        if packet.get("labeling_status") == "reviewed":
            packet = {**packet, "labeling_status": "completed_human_review"}
        contrastive_packets.append(packet)
    contrastive = evaluate_packets(contrastive_packets, embed_claims, embed_evidence)
    contrastive.update({"embedding_model": "intfloat/multilingual-e5-small", "label_source": "independent_human_contrastive_review"})
    report = {"round": 68, "scope": "independent_tier_verification", "output_validation": output, "contrastive": contrastive}
    (OUT / "round68_output_evaluation.json").write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (OUT / "round68_contrastive_evaluation.json").write_text(json.dumps(contrastive, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (OUT / "round68_independent_evaluation.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


if __name__ == "__main__": print(json.dumps(evaluate(), ensure_ascii=False, indent=2))
