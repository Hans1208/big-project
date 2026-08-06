"""Train on the fixed training split, calibrate on validation, report held-out test metrics."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from evaluation import cluster_bootstrap_intervals, evaluate_hallucination_predictions, select_threshold_by_f1
from training import FEATURE_NAMES, FEATURE_NAMES_V2, load_jsonl, mlp_probability, save_model, train_mlp


def _rows_for(rows: list[dict[str, Any]], case_ids: set[str]) -> list[dict[str, Any]]:
    return [row for row in rows if row.get("case_id") in case_ids]


def _require_both_classes(rows: list[dict[str, Any]], split: str) -> None:
    labels = {row["is_hallucination"] for row in rows}
    if labels != {False, True}:
        raise ValueError(f"{split} split needs both supported and hallucination labels before accuracy can be trusted")


def evaluate_fixed_split(
    rows: list[dict[str, Any]], split: dict[str, Any], feature_names: tuple[str, ...] = FEATURE_NAMES,
) -> tuple[dict[str, Any], dict[str, Any]]:
    assignments = {name: set(ids) for name, ids in split["assignments"].items()}
    used_cases = set().union(*assignments.values())
    unknown = {row["case_id"] for row in rows} - used_cases
    if unknown:
        raise ValueError(f"training rows contain unassigned case_ids: {sorted(unknown)}")
    train_rows, validation_rows, test_rows = (_rows_for(rows, assignments[name]) for name in ("train", "validation", "test"))
    if not train_rows or not validation_rows or not test_rows:
        raise ValueError("all train/validation/test partitions need completed human labels")
    _require_both_classes(validation_rows, "validation")
    _require_both_classes(test_rows, "test")
    model = train_mlp(train_rows, feature_names=feature_names)
    validation_probs = [mlp_probability(row["features"], model) for row in validation_rows]
    threshold = select_threshold_by_f1([row["is_hallucination"] for row in validation_rows], validation_probs)
    test_probs = [mlp_probability(row["features"], model) for row in test_rows]
    test_metrics = evaluate_hallucination_predictions([row["is_hallucination"] for row in test_rows], test_probs, threshold.threshold)
    report = {
        "evaluation_version": "fixed_split_v1",
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
        "split_version": split["split_version"],
        "split_counts": {name: len(_rows_for(rows, ids)) for name, ids in assignments.items()},
        "selected_threshold": threshold.threshold,
        "validation": asdict(threshold.metrics),
        "test": asdict(test_metrics),
        "test_case_clustered_95ci": {name: list(interval) for name, interval in cluster_bootstrap_intervals([row["case_id"] for row in test_rows], [row["is_hallucination"] for row in test_rows], test_probs, threshold.threshold).items()},
        "warning": "Metrics are preliminary for small labelled sets; report the held-out test score, not training accuracy.",
    }
    return model, report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run label-gated fixed-split MLP evaluation and append a metrics history record.")
    parser.add_argument("--rows", type=Path, default=Path("data/training/training_rows.jsonl"))
    parser.add_argument("--split", type=Path, default=Path("data/splits/case_split_v1.json"))
    parser.add_argument("--model-output", type=Path, default=Path("models/candidates/mlp_candidate.json"))
    parser.add_argument("--history", type=Path, default=Path("data/metrics/metrics_history.jsonl"))
    parser.add_argument("--feature-contract", choices=("v1", "v2"), default="v1")
    args = parser.parse_args()
    feature_names = FEATURE_NAMES_V2 if args.feature_contract == "v2" else FEATURE_NAMES
    model, report = evaluate_fixed_split(load_jsonl(args.rows, feature_names), json.loads(args.split.read_text(encoding="utf-8")), feature_names)
    report["feature_contract"] = args.feature_contract
    save_model(model, args.model_output)
    args.history.parent.mkdir(parents=True, exist_ok=True)
    with args.history.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(report, ensure_ascii=False) + "\n")
    print(json.dumps(report, ensure_ascii=False, indent=2))
