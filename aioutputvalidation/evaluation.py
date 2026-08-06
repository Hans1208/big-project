"""Small, dependency-free binary-classification metrics for hallucination evaluation."""

from __future__ import annotations

from dataclasses import dataclass
import random
from typing import Sequence

from policy import load_policy


@dataclass(frozen=True)
class EvaluationMetrics:
    threshold: float
    true_positive: int
    false_positive: int
    true_negative: int
    false_negative: int
    accuracy: float
    precision: float
    recall: float
    f1: float


@dataclass(frozen=True)
class ThresholdSelection:
    threshold: float
    metrics: EvaluationMetrics


def evaluate_hallucination_predictions(
    labels: Sequence[bool], probabilities: Sequence[float], threshold: float = 0.70
) -> EvaluationMetrics:
    """Evaluate predicted hallucination probabilities against adjudicated labels."""
    if len(labels) != len(probabilities):
        raise ValueError("labels and probabilities must have the same length")
    if not 0 <= threshold <= 1:
        raise ValueError("threshold must be between 0 and 1")
    if any(not 0 <= probability <= 1 for probability in probabilities):
        raise ValueError("probabilities must be between 0 and 1")

    tp = fp = tn = fn = 0
    for label, probability in zip(labels, probabilities):
        predicted = probability >= threshold
        if label and predicted:
            tp += 1
        elif not label and predicted:
            fp += 1
        elif not label and not predicted:
            tn += 1
        else:
            fn += 1
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    total = tp + fp + tn + fn
    accuracy = (tp + tn) / total if total else 0.0
    return EvaluationMetrics(threshold, tp, fp, tn, fn, round(accuracy, 4), round(precision, 4), round(recall, 4), round(f1, 4))


def select_threshold_by_f1(
    labels: Sequence[bool], probabilities: Sequence[float], minimum_recall: float | None = None
) -> ThresholdSelection:
    """Choose the highest-F1 operating threshold that preserves safety recall."""
    minimum_recall = load_policy().minimum_recall_target if minimum_recall is None else minimum_recall
    if not 0 <= minimum_recall <= 1:
        raise ValueError("minimum_recall must be between 0 and 1")
    candidates = sorted(set(probabilities) | {0.0, 1.0})
    metrics_by_threshold = [evaluate_hallucination_predictions(labels, probabilities, threshold) for threshold in candidates]
    eligible = [metrics for metrics in metrics_by_threshold if metrics.recall >= minimum_recall]
    if not eligible:
        raise ValueError("no threshold meets minimum_recall")
    best = max(eligible, key=lambda metric: (metric.f1, metric.precision, metric.threshold))
    return ThresholdSelection(best.threshold, best)


def cluster_bootstrap_intervals(
    case_ids: Sequence[str], labels: Sequence[bool], probabilities: Sequence[float], threshold: float, iterations: int = 500, seed: int = 42
) -> dict[str, tuple[float, float]]:
    """95% percentile intervals, resampling complete cases to avoid claim leakage."""
    if not (len(case_ids) == len(labels) == len(probabilities)):
        raise ValueError("case_ids, labels, and probabilities must have the same length")
    by_case: dict[str, list[int]] = {}
    for index, case_id in enumerate(case_ids):
        by_case.setdefault(case_id, []).append(index)
    if not by_case or iterations < 20:
        raise ValueError("at least one case and 20 bootstrap iterations are required")
    rng, cases = random.Random(seed), sorted(by_case)
    values = {name: [] for name in ("accuracy", "precision", "recall", "f1")}
    for _ in range(iterations):
        chosen = [rng.choice(cases) for _ in cases]
        indices = [index for case_id in chosen for index in by_case[case_id]]
        metrics = evaluate_hallucination_predictions([labels[index] for index in indices], [probabilities[index] for index in indices], threshold)
        for name in values:
            values[name].append(getattr(metrics, name))
    def percentile(numbers: list[float], fraction: float) -> float:
        ordered = sorted(numbers)
        return ordered[round((len(ordered) - 1) * fraction)]
    return {name: (round(percentile(numbers, 0.025), 4), round(percentile(numbers, 0.975), 4)) for name, numbers in values.items()}
