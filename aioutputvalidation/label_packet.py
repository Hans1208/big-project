"""Prepare blank human-label packets from API-generated candidate outputs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from integration import extract_claims


def build_label_packet(bundle: dict[str, Any], bundle_path: Path) -> dict[str, Any]:
    claims = extract_claims(bundle["ai_output"])
    return {
        "case_id": bundle["case_id"],
        "candidate_output_path": str(bundle_path).replace("\\", "/"),
        "answer_generator": bundle["answer_generator"],
        "reviewer_id": None,
        "claims": [
            {"claim_id": f"{bundle['case_id']}-C{index:02d}", "text": claim, "is_supported": None, "is_hallucination": None, "evidence_ids": [], "reviewer_rationale": None}
            for index, claim in enumerate(claims, start=1)
        ],
        "labeling_status": "pending_human_review",
        "instruction": "Human reviewer must label independently. Do not copy model confidence or inferred gold answers into this file.",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Create blank human label packets from generated AI outputs.")
    parser.add_argument("--input-dir", type=Path, default=Path("data/03_ai_outputs/generated"))
    parser.add_argument("--output-dir", type=Path, default=Path("data/04_gold_labels/label_packets"))
    parser.add_argument("--only-missing", action="store_true", help="Never overwrite a packet a human may already be reviewing.")
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for bundle_path in sorted(args.input_dir.glob("SYN-*.json")):
        bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
        packet = build_label_packet(bundle, bundle_path)
        output = args.output_dir / bundle_path.name
        if args.only_missing and output.exists():
            print(f"Skipped existing {output}")
            continue
        output.write_text(json.dumps(packet, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Created {output}")
