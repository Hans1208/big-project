"""Prepare blank human packets for claim-to-evidence contrastive labels."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from integration import extract_claims
from observation_builder import split_evidence_chunks


def build_contrastive_packet(bundle: dict[str, Any], transcript: str, bundle_path: Path) -> dict[str, Any]:
    """Build a blind packet with source chunks but no scores, ranks, or labels."""
    case_id = bundle["case_id"]
    claims = extract_claims(bundle["ai_output"])
    chunks = split_evidence_chunks(transcript)
    return {
        "case_id": case_id,
        "candidate_output_path": str(bundle_path).replace("\\", "/"),
        "reviewer_id": None,
        "reviewer_role": "independent_contrastive_reviewer",
        "claims": [
            {
                "claim_id": f"{case_id}-C{index:02d}",
                "text": claim,
                "support_status": None,
                "supporting_evidence_id": None,
                "hard_negative_evidence_id": None,
                "reviewer_rationale": None,
            }
            for index, claim in enumerate(claims, start=1)
        ],
        "evidence_chunks": [
            {"evidence_id": f"{case_id}:E{index:02d}", "text": chunk}
            for index, chunk in enumerate(chunks, start=1)
        ],
        "labeling_status": "pending_human_review",
        "instruction": (
            "Review independently. For each claim, mark support_status as supported or unsupported. "
            "For supported claims select one directly supporting chunk and, when another plausible but non-supporting chunk exists, one hard negative. "
            "Do not use model scores, rankings, prior labels, or inferred gold answers."
        ),
    }


def validate_completed_packet(packet: dict[str, Any]) -> None:
    """Reject incomplete or internally inconsistent human contrastive labels."""
    if packet.get("labeling_status") != "completed_human_review" or not packet.get("reviewer_id"):
        raise ValueError("completed packet needs reviewer_id and completed_human_review status")
    evidence_ids = {item["evidence_id"] for item in packet.get("evidence_chunks", [])}
    if not evidence_ids:
        raise ValueError("packet needs evidence chunks")
    for claim in packet.get("claims", []):
        status = claim.get("support_status")
        support = claim.get("supporting_evidence_id")
        negative = claim.get("hard_negative_evidence_id")
        if status not in {"supported", "unsupported"}:
            raise ValueError("each claim needs supported or unsupported status")
        if status == "supported" and support not in evidence_ids:
            raise ValueError("supported claim needs a valid supporting evidence id")
        if status == "unsupported" and support is not None:
            raise ValueError("unsupported claim cannot select supporting evidence")
        if negative is not None and negative not in evidence_ids:
            raise ValueError("hard negative must reference an evidence chunk")
        if support is not None and support == negative:
            raise ValueError("supporting evidence and hard negative must differ")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Create blank contrastive human-label packets without rankings or scores.")
    parser.add_argument("--catalog", type=Path, default=Path("data/scenario_catalog.json"))
    parser.add_argument("--bundle-dir", type=Path, default=Path("data/03_ai_outputs/generated"))
    parser.add_argument("--output-dir", type=Path, default=Path("data/61_contrastive_diagnostic/label_packets"))
    parser.add_argument("--only-missing", action="store_true")
    args = parser.parse_args()
    catalog = {item["case_id"]: item for item in json.loads(args.catalog.read_text(encoding="utf-8"))}
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for bundle_path in sorted(args.bundle_dir.glob("SYN-*.json")):
        bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
        transcript = (args.catalog.parent / catalog[bundle["case_id"]]["transcript_path"]).read_text(encoding="utf-8")
        destination = args.output_dir / bundle_path.name
        if args.only_missing and destination.exists():
            continue
        destination.write_text(json.dumps(build_contrastive_packet(bundle, transcript, bundle_path), ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Created {destination}")
