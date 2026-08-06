"""Offline batch validation for de-identified evaluation records."""

from __future__ import annotations

import json
import argparse
from pathlib import Path
from typing import Any

from audit import build_audit_record
from validator import validate


def validate_records(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Validate pre-embedded records and return an aggregate report plus audits."""
    audits: list[dict[str, Any]] = []
    counts = {"safe": 0, "review_required": 0, "high_risk": 0}
    for index, record in enumerate(records, start=1):
        result = validate(
            record["ai_output"],
            record.get("claim_embeddings", []),
            record.get("evidence_embeddings", []),
            cited_claim_count=int(record.get("cited_claim_count", 0)),
            uncertainty_disclosed=bool(record.get("uncertainty_disclosed", False)),
        )
        counts[result.decision] += 1
        audit = build_audit_record(result)
        audit["record_id"] = str(record.get("record_id", f"record-{index}"))
        audits.append(audit)
    return {"total_records": len(records), "decision_counts": counts, "audits": audits}


def run_jsonl(input_path: Path, output_path: Path) -> None:
    records = [json.loads(line) for line in input_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    output_path.write_text(json.dumps(validate_records(records), ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run de-identified AI output validation over JSONL records.")
    parser.add_argument("input", type=Path, help="Input JSONL with precomputed embeddings")
    parser.add_argument("output", type=Path, help="Destination JSON audit report")
    arguments = parser.parse_args()
    run_jsonl(arguments.input, arguments.output)
