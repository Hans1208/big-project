"""Train and version the 5→8→1 hallucination MLP from approved feature labels."""

from __future__ import annotations

import json
import math
import random
from pathlib import Path
from typing import Any


FEATURE_NAMES = ("schema_error", "evidence_gap", "low_support_ratio", "citation_missing_ratio", "uncertainty_absent")
FEATURE_NAMES_V2 = FEATURE_NAMES + (
    "evidence_ambiguity",
    "explicit_conflict_present",
    "unsupported_assertion_present",
)


def load_jsonl(path: Path, feature_names: tuple[str, ...] = FEATURE_NAMES) -> list[dict[str, Any]]:
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    for row in rows:
        if set(row.get("features", {})) != set(feature_names) or not isinstance(row.get("is_hallucination"), bool):
            raise ValueError("each row needs the selected named feature contract and a boolean is_hallucination")
    return rows


def _sigmoid(value: float) -> float:
    return 1.0 / (1.0 + math.exp(-max(-35.0, min(35.0, value))))


def train_mlp(
    rows: list[dict[str, Any]], epochs: int = 300, learning_rate: float = 0.05, seed: int = 42,
    feature_names: tuple[str, ...] = FEATURE_NAMES,
) -> dict[str, Any]:
    """Deterministic SGD training with ReLU hidden layer and BCE loss."""
    if not rows:
        raise ValueError("at least one labelled row is required")
    rng = random.Random(seed)
    if any(set(row["features"]) != set(feature_names) for row in rows):
        raise ValueError("each training row must use the selected feature contract")
    w1 = [[rng.uniform(-0.2, 0.2) for _ in feature_names] for _ in range(8)]
    b1 = [0.0] * 8
    w2 = [rng.uniform(-0.2, 0.2) for _ in range(8)]
    b2 = 0.0
    for _ in range(epochs):
        for row in rows:
            x = [float(row["features"][name]) for name in feature_names]
            y = float(row["is_hallucination"])
            pre_hidden = [sum(weight * value for weight, value in zip(weights, x)) + bias for weights, bias in zip(w1, b1)]
            hidden = [max(0.0, value) for value in pre_hidden]
            prediction = _sigmoid(sum(weight * value for weight, value in zip(w2, hidden)) + b2)
            output_error = prediction - y
            old_w2 = list(w2)
            for index in range(8):
                w2[index] -= learning_rate * output_error * hidden[index]
            b2 -= learning_rate * output_error
            for neuron in range(8):
                hidden_error = output_error * old_w2[neuron] * float(pre_hidden[neuron] > 0)
                for feature in range(len(feature_names)):
                    w1[neuron][feature] -= learning_rate * hidden_error * x[feature]
                b1[neuron] -= learning_rate * hidden_error
    return {
        "model_name": "hallucination_mlp", "model_version": "candidate-trained", "architecture": [len(feature_names), 8, 1],
        "training_status": "trained_on_labelled_features", "weights_1": w1, "bias_1": b1, "weights_2": w2, "bias_2": b2,
        "feature_names": list(feature_names), "seed": seed, "epochs": epochs, "learning_rate": learning_rate,
    }


def save_model(model: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(model, ensure_ascii=False, indent=2), encoding="utf-8")


def mlp_probability(features: dict[str, float], model: dict[str, Any]) -> float:
    """Run an in-memory candidate model; used only by held-out evaluation."""
    names = tuple(model.get("feature_names", FEATURE_NAMES))
    values = [float(features[name]) for name in names]
    hidden = [max(0.0, sum(w * x for w, x in zip(row, values)) + bias) for row, bias in zip(model["weights_1"], model["bias_1"])]
    logit = sum(w * x for w, x in zip(model["weights_2"], hidden)) + model["bias_2"]
    return _sigmoid(logit)
