"""Retrain a shadow MLP from Round 3–7 human output reviews; excludes Round 8."""

from __future__ import annotations

import json
from pathlib import Path

from model_evaluation import evaluate_fixed_split
from training import load_jsonl, save_model


def round_split(rows: list[dict]) -> dict:
    assignments = {"train": [], "validation": [], "test": []}
    for row in rows:
        case_id = row["case_id"]
        if case_id.startswith(("SYN-R3-", "SYN-R4-", "SYN-R5-")):
            assignments["train"].append(case_id)
        elif case_id.startswith("SYN-R6-"):
            assignments["validation"].append(case_id)
        elif case_id.startswith("SYN-R7-"):
            assignments["test"].append(case_id)
        else:
            raise ValueError(f"unexpected training case: {case_id}")
    return {"split_version": "output_feedback_round_split_v1", "assignments": {name: sorted(set(ids)) for name, ids in assignments.items()}}


if __name__ == "__main__":
    rows_path = Path("data/training/output_feedback_rows_r3_r7.jsonl")
    rows = load_jsonl(rows_path)
    model, report = evaluate_fixed_split(rows, round_split(rows))
    model["model_version"] = "output_feedback_mlp_v2"
    model["training_status"] = "shadow_candidate_from_round3_to_round7_human_output_reviews"
    model_path = Path("models/candidates/output_feedback_mlp_v2.json")
    report_path = Path("data/16_round9_retraining/retraining_report.json")
    manifest_path = Path("models/candidates/output_feedback_mlp_v2_manifest.json")
    save_model(model, model_path)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    manifest_path.write_text(json.dumps({
        "active_model_version": model["model_version"], "runtime_mode": "shadow", "model_path": str(model_path),
        "decision_threshold": report["selected_threshold"], "evaluation_version": report["evaluation_version"],
        "activation_requirement": "Round 8 is excluded; evaluate this candidate on newly generated Round 9 data before promotion.",
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
