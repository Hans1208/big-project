"""Versioned decision policy for reproducible validation outcomes."""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


@dataclass(frozen=True)
class ValidationPolicy:
    policy_name: str
    policy_version: str
    evidence_support_threshold: float
    review_probability_threshold: float
    high_risk_probability_threshold: float
    minimum_recall_target: float


@lru_cache(maxsize=1)
def load_policy() -> ValidationPolicy:
    path = Path(__file__).parent / "models" / "validation_policy_v0.json"
    raw = json.loads(path.read_text(encoding="utf-8"))
    policy = ValidationPolicy(**raw)
    thresholds = (policy.evidence_support_threshold, policy.review_probability_threshold, policy.high_risk_probability_threshold, policy.minimum_recall_target)
    if any(value < 0 or value > 1 for value in thresholds):
        raise ValueError("policy thresholds must be between 0 and 1")
    if policy.review_probability_threshold > policy.high_risk_probability_threshold:
        raise ValueError("review threshold cannot exceed high-risk threshold")
    return policy
