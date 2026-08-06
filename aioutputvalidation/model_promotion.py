"""Promote an evaluated MLP only when the validation safety gate passes."""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from policy import load_policy


def promote(candidate: Path, report: dict, root: Path) -> Path:
    validation = report["validation"]
    policy = load_policy()
    if validation["recall"] < policy.minimum_recall_target:
        raise ValueError(f"promotion blocked: validation recall {validation['recall']} is below {policy.minimum_recall_target}")
    if validation["f1"] <= 0:
        raise ValueError("promotion blocked: validation F1 must be positive")
    active_dir = root / "models" / "active"
    active_dir.mkdir(parents=True, exist_ok=True)
    active_model = active_dir / "mlp_weights_v1.json"
    shutil.copyfile(candidate, active_model)
    manifest = {
        "active_model_version": "mlp_weights_v1",
        "runtime_mode": "shadow",
        "model_path": "models/active/mlp_weights_v1.json",
        "decision_threshold": report["selected_threshold"],
        "promotion_gate": {"minimum_validation_recall": policy.minimum_recall_target, "validation_recall": validation["recall"], "validation_f1": validation["f1"]},
        "evaluation_version": report["evaluation_version"],
        "activation_requirement": "Validate identical feature extraction against the backend RAG request before changing runtime_mode to active.",
    }
    manifest_path = active_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Promote a validation-approved candidate MLP.")
    parser.add_argument("--candidate", type=Path, default=Path("models/candidates/mlp_candidate.json"))
    parser.add_argument("--history", type=Path, default=Path("data/metrics/metrics_history.jsonl"))
    args = parser.parse_args()
    report = json.loads(args.history.read_text(encoding="utf-8").splitlines()[-1])
    print(promote(args.candidate, report, Path(".").resolve()))
