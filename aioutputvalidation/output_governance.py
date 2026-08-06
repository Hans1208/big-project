"""Prevent role leakage before independently generated AI outputs are evaluated."""

from __future__ import annotations

from typing import Any

from integration_readiness import find_analysis_contract_gaps
from validator import schema_errors


FORBIDDEN_LABEL_FIELDS = {"is_hallucination", "is_supported", "gold_label", "adjudicated_label", "gold_evidence_id"}


def validate_output_bundle(bundle: dict[str, Any], manifest_record: dict[str, Any]) -> list[str]:
    """Check that answer generation is independent from scenario creation and labels."""
    errors: list[str] = []
    if bundle.get("case_id") != manifest_record.get("case_id"):
        errors.append("bundle case_id does not match manifest")
    generator = str(bundle.get("answer_generator", "")).strip()
    if not generator:
        errors.append("answer_generator is required")
    elif generator != manifest_record.get("answer_generator"):
        errors.append("answer_generator does not match assigned manifest role")
    if generator in {manifest_record.get("scenario_author"), manifest_record.get("gold_labeler")}:
        errors.append("answer generator must be distinct from scenario author and gold labeler")
    if FORBIDDEN_LABEL_FIELDS & bundle.keys():
        errors.append("AI output bundle must not contain gold-label fields")
    ai_output = bundle.get("ai_output")
    if not isinstance(ai_output, dict):
        errors.append("ai_output must be an object")
    else:
        errors.extend(find_analysis_contract_gaps(ai_output))
        errors.extend(f"AI output schema: {error}" for error in schema_errors(ai_output))
    rag_results = bundle.get("rag_results")
    if not isinstance(rag_results, list):
        errors.append("rag_results must be an array")
    return errors
