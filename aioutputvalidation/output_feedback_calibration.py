"""Calibrate output-risk threshold from blind human output-review feedback."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from evaluation import evaluate_hallucination_predictions, select_threshold_by_f1


def collect(results_dir: Path, feedback_dirs: list[Path]) -> tuple[list[bool], list[float]]:
    labels, probabilities = [], []
    seen: set[str] = set()
    for directory in feedback_dirs:
        for path in sorted(directory.glob("SYN-*.json")):
            feedback = json.loads(path.read_text(encoding="utf-8"))
            if feedback.get("review_status") != "completed_human_output_review":
                raise ValueError(f"incomplete feedback: {path.name}")
            if path.name in seen:
                raise ValueError(f"duplicate feedback case: {path.name}")
            seen.add(path.name)
            result = json.loads((results_dir / path.name).read_text(encoding="utf-8"))
            labels.append(feedback["reviewer_decision"] != "safe")
            probabilities.append(float(result["hallucination_probability"]))
    return labels, probabilities


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Create a shadow-only threshold calibration from human output-review feedback.")
    parser.add_argument("--results-dir", type=Path, default=Path("data/07_validation_results"))
    parser.add_argument("--feedback-dirs", type=Path, nargs="+", default=[Path("data/08_output_review_feedback/packets"), Path("data/09_safe_output_review_feedback/packets")])
    parser.add_argument("--manifest", type=Path, default=Path("models/active/manifest.json"))
    parser.add_argument("--output", type=Path, default=Path("data/metrics/output_feedback_calibration.json"))
    args = parser.parse_args()
    labels, probabilities = collect(args.results_dir, args.feedback_dirs)
    if len(set(labels)) != 2:
        raise SystemExit("need both safe and non-safe human decisions for calibration")
    current = json.loads(args.manifest.read_text(encoding="utf-8"))["decision_threshold"]
    selection = select_threshold_by_f1(labels, probabilities)
    report = {
        "calibration_mode": "shadow_only",
        "reviewed_outputs": len(labels),
        "human_non_safe_outputs": sum(labels),
        "current_threshold": current,
        "current_metrics": evaluate_hallucination_predictions(labels, probabilities, current).__dict__,
        "selected_threshold": selection.threshold,
        "selected_metrics": selection.metrics.__dict__,
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
        "warning": "This is calibration data, not an independent performance test. Confirm on a fresh blind batch before activation.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
