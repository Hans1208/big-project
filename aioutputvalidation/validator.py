"""Dependency-light AI output validation prototype for capstone evaluation."""

from __future__ import annotations

import math
import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable, Sequence

from jsonschema import Draft202012Validator

from policy import load_policy
from training import FEATURE_NAMES


SUPPORT_THRESHOLD = load_policy().evidence_support_threshold


@dataclass(frozen=True)
class ValidationResult:
    valid: bool
    schema_errors: list[str]
    evidence_score: float
    claim_evidence_scores: list[float]
    hallucination_probability: float
    decision: str

    def to_dict(self) -> dict[str, Any]:
        """Return an API/JSON-ready record without retaining source consultation text."""
        return {
            "valid": self.valid,
            "schema_errors": self.schema_errors,
            "evidence_score": self.evidence_score,
            "claim_evidence_scores": self.claim_evidence_scores,
            "hallucination_probability": self.hallucination_probability,
            "decision": self.decision,
        }


def cosine_similarity(left: Sequence[float], right: Sequence[float]) -> float:
    """Return cosine similarity, safely handling empty or zero vectors."""
    if len(left) != len(right) or not left:
        return 0.0
    numerator = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(a * a for a in left))
    right_norm = math.sqrt(sum(b * b for b in right))
    return numerator / (left_norm * right_norm) if left_norm and right_norm else 0.0


def schema_errors(payload: Any) -> list[str]:
    """Validate directly against the project JSON Schema document."""
    schema_path = Path(__file__).parent / "schema" / "ai_analysis.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)
    return [f"{'.'.join(map(str, error.absolute_path)) or 'root'}: {error.message}" for error in sorted(validator.iter_errors(payload), key=str)]


def evidence_scores(claim_embeddings: Iterable[Sequence[float]], evidence_embeddings: Iterable[Sequence[float]]) -> list[float]:
    """Contrastive-learning inference: each claim gets its most similar evidence."""
    evidence = list(evidence_embeddings)
    return [max((cosine_similarity(claim, item) for item in evidence), default=0.0) for claim in claim_embeddings]


@lru_cache(maxsize=2)
def _load_model_at(path_text: str) -> dict[str, Any]:
    path = Path(path_text)
    model = json.loads(path.read_text(encoding="utf-8"))
    feature_names = model.get("feature_names", FEATURE_NAMES)
    architecture = model.get("architecture")
    if architecture is None or architecture[0] != len(feature_names) or architecture[-1] != 1:
        raise ValueError("unsupported hallucination model architecture")
    return model


def load_runtime() -> tuple[dict[str, Any], float | None]:
    """Load a locally promoted candidate, or the immutable baseline when absent."""
    root = Path(__file__).parent
    manifest_path = root / "models" / "active" / "manifest.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        # A promoted model remains shadow-only until production feature parity is proven.
        if manifest.get("runtime_mode") == "active":
            path = root / manifest["model_path"]
            return _load_model_at(str(path)), float(manifest["decision_threshold"])
    return _load_model_at(str(root / "models" / "mlp_weights_v0.json")), None


def load_model_weights() -> dict[str, Any]:
    """Compatibility accessor for the active local model weights."""
    return load_runtime()[0]


def _mlp_probability(features: dict[str, float]) -> float:
    """Run the versioned MLP weights, ordering inputs by the model's own feature_names."""
    model = load_model_weights()
    names = tuple(model.get("feature_names", FEATURE_NAMES))
    values = [float(features[name]) for name in names]
    hidden = [max(0.0, sum(w * x for w, x in zip(row, values)) + bias) for row, bias in zip(model["weights_1"], model["bias_1"])]
    logit = sum(w * x for w, x in zip(model["weights_2"], hidden)) + model["bias_2"]
    return 1.0 / (1.0 + math.exp(-logit))


def validate(payload: Any, claim_embeddings: Iterable[Sequence[float]], evidence_embeddings: Iterable[Sequence[float]], cited_claim_count: int = 0, uncertainty_disclosed: bool = False) -> ValidationResult:
    """Run the three-stage validation pipeline and return an auditable decision."""
    errors = schema_errors(payload)
    claim_vectors = list(claim_embeddings)
    scores = evidence_scores(claim_vectors, evidence_embeddings)
    evidence_score = sum(scores) / len(scores) if scores else 0.0
    low_support_ratio = sum(score < SUPPORT_THRESHOLD for score in scores) / len(scores) if scores else 1.0
    citation_missing_ratio = max(0, len(claim_vectors) - cited_claim_count) / len(claim_vectors) if claim_vectors else 1.0
    features = {
        "schema_error": float(bool(errors)),
        "evidence_gap": 1 - evidence_score,
        "low_support_ratio": low_support_ratio,
        "citation_missing_ratio": citation_missing_ratio,
        "uncertainty_absent": float(low_support_ratio > 0 and not uncertainty_disclosed),
    }
    probability = _mlp_probability(features)
    policy = load_policy()
    _, calibrated_threshold = load_runtime()
    high_risk_threshold = calibrated_threshold if calibrated_threshold is not None else policy.high_risk_probability_threshold
    review_threshold = min(policy.review_probability_threshold, high_risk_threshold * 0.8)
    if errors or probability >= high_risk_threshold:
        decision = "high_risk"
    elif probability >= review_threshold or low_support_ratio > 0:
        decision = "review_required"
    else:
        decision = "safe"
    return ValidationResult(
        not errors,
        errors,
        round(evidence_score, 4),
        [round(score, 4) for score in scores],
        round(probability, 4),
        decision,
    )
