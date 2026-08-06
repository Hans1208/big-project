"""Privacy-preserving audit records for reviewer queues and capstone demonstrations."""

from __future__ import annotations

from typing import Any

from validator import SUPPORT_THRESHOLD, ValidationResult, load_model_weights, load_runtime
from policy import load_policy


def build_audit_record(result: ValidationResult) -> dict[str, Any]:
    """Summarise why review is needed without copying consultation or evidence text."""
    reasons: list[str] = []
    if result.schema_errors:
        reasons.append("JSON Schema validation failed")
    weak_claims = [index + 1 for index, score in enumerate(result.claim_evidence_scores) if score < SUPPORT_THRESHOLD]
    if weak_claims:
        reasons.append(f"weak evidence for claim indexes: {weak_claims}")
    # Mirror validate()'s own threshold selection so this explanation can never disagree
    # with the decision it is describing (a promoted model's calibrated threshold
    # overrides the static policy threshold there too).
    _, calibrated_threshold = load_runtime()
    high_risk_threshold = calibrated_threshold if calibrated_threshold is not None else load_policy().high_risk_probability_threshold
    if result.hallucination_probability >= high_risk_threshold:
        reasons.append("hallucination probability exceeded high-risk threshold")
    elif result.decision == "review_required":
        reasons.append("manual review threshold triggered")
    model = load_model_weights()
    return {
        "contract_version": "1.0",
        "model_name": model["model_name"],
        "model_version": model["model_version"],
        "policy_version": load_policy().policy_version,
        "decision": result.decision,
        "validation": result.to_dict(),
        "review_reasons": reasons,
        "privacy_note": "No consultation text, evidence text, personal data, or credentials are retained in this record.",
    }
