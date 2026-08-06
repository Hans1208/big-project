"""Check whether a captured AI result is complete enough for output validation."""

from __future__ import annotations

from typing import Any


FULL_ANALYSIS_FIELDS = {
    "summary", "case_type", "case_subtype", "urgency_level", "eligibility",
    "extracted_json", "missing_info_json", "checklist_json", "timeline_json",
}


def find_analysis_contract_gaps(payload: dict[str, Any]) -> list[str]:
    """Block validation if the full structured LLM output was projected or truncated."""
    missing = sorted(FULL_ANALYSIS_FIELDS - payload.keys())
    return [f"full analysis payload missing: {field}" for field in missing]


def find_consult_response_gaps(response: dict[str, Any]) -> list[str]:
    """Diagnose the current /consult/analyze projection without inventing missing values."""
    errors: list[str] = []
    for field in ("consult_summary", "consult_case_type", "consult_case_subtype", "consult_extracted", "consult_timeline"):
        if field not in response:
            errors.append(f"consult response missing: {field}")
    for field in ("related_statutes", "related_precedents"):
        if field not in response:
            errors.append(f"consult response missing RAG sources: {field}")
    # The response projection exposes only five analysis fields. The remaining
    # four must be preserved from the original Pydantic result for schema validation.
    errors.extend(
        f"full analysis projection required before validation: {field}"
        for field in ("urgency_level", "eligibility", "missing_info_json", "checklist_json")
    )
    return errors
