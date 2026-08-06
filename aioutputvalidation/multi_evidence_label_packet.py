"""Prepare a follow-up human review for all direct supporting evidence chunks."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def build_multi_evidence_packet(source: dict) -> dict:
    """Make a score-free follow-up packet without copying prior evidence choices."""
    supported = [claim for claim in source["claims"] if claim.get("support_status") == "supported"]
    return {
        "case_id": source["case_id"],
        "reviewer_id": None,
        "reviewer_role": "multi_evidence_clarification_reviewer",
        "claims": [
            {"claim_id": claim["claim_id"], "text": claim["text"], "supporting_evidence_ids": [], "reviewer_rationale": None}
            for claim in supported
        ],
        "evidence_chunks": source["evidence_chunks"],
        "labeling_status": "pending_human_review",
        "instruction": "For each listed supported claim, select every evidence chunk that directly supports any material fact in the claim. Do not select merely related chunks. Do not use model scores or rankings.",
    }


def validate_completed_packet(packet: dict) -> None:
    if packet.get("labeling_status") != "completed_human_review" or not packet.get("reviewer_id"):
        raise ValueError("completed packet needs reviewer_id and completed_human_review status")
    available = {item["evidence_id"] for item in packet.get("evidence_chunks", [])}
    for claim in packet.get("claims", []):
        selected = claim.get("supporting_evidence_ids")
        if not isinstance(selected, list) or not selected or not set(selected) <= available:
            raise ValueError("each supported claim needs one or more valid evidence ids")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Create blank multi-positive evidence clarification packets.")
    parser.add_argument("--source-dir", type=Path, default=Path("data/61_contrastive_diagnostic/label_packets"))
    parser.add_argument("--output-dir", type=Path, default=Path("data/62_multi_evidence_clarification/label_packets"))
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for path in sorted(args.source_dir.glob("SYN-*.json")):
        destination = args.output_dir / path.name
        if destination.exists():
            continue
        source = json.loads(path.read_text(encoding="utf-8"))
        destination.write_text(json.dumps(build_multi_evidence_packet(source), ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Created {destination}")
