"""Block incomplete or self-labelled packets before training and evaluation."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any


def packet_errors(packet: dict[str, Any], scenario_author: str | None = None) -> list[str]:
    errors: list[str] = []
    reviewer = str(packet.get("reviewer_id") or "").strip()
    if not reviewer:
        errors.append("reviewer_id is required")
    if reviewer and reviewer == packet.get("answer_generator"):
        errors.append("reviewer_id must differ from answer_generator")
    if reviewer and scenario_author and reviewer == scenario_author:
        errors.append("reviewer_id must differ from scenario_author")
    if packet.get("labeling_status") != "completed_human_review":
        errors.append("labeling_status must be completed_human_review")
    claims = packet.get("claims")
    if not isinstance(claims, list) or not claims:
        errors.append("at least one claim is required")
        return errors
    for claim in claims:
        if not isinstance(claim.get("is_supported"), bool):
            errors.append(f"{claim.get('claim_id', 'claim')}: is_supported must be boolean")
        if not isinstance(claim.get("is_hallucination"), bool):
            errors.append(f"{claim.get('claim_id', 'claim')}: is_hallucination must be boolean")
    return errors


def summarize_packets(packets: list[dict[str, Any]], difficulty_by_case: dict[str, str]) -> dict[str, Any]:
    hallucination_counts = Counter()
    difficulty_counts = Counter()
    claim_count = 0
    for packet in packets:
        difficulty_counts[difficulty_by_case.get(packet["case_id"], "unknown")] += 1
        for claim in packet.get("claims", []):
            claim_count += 1
            hallucination_counts[str(claim.get("is_hallucination"))] += 1
    return {"packets": len(packets), "claims": claim_count, "packets_by_difficulty": dict(difficulty_counts), "hallucination_labels": dict(hallucination_counts)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Validate completed human label packets before model training.")
    parser.add_argument("--packet-dir", type=Path, default=Path("data/04_gold_labels/label_packets"))
    parser.add_argument("--catalog", type=Path, default=Path("data/scenario_catalog.json"))
    args = parser.parse_args()
    catalog = json.loads(args.catalog.read_text(encoding="utf-8"))
    difficulties = {item["case_id"]: item["difficulty"] for item in catalog}
    packets = [json.loads(path.read_text(encoding="utf-8")) for path in sorted(args.packet_dir.glob("SYN-*.json"))]
    errors = [f"{packet['case_id']}: {error}" for packet in packets for error in packet_errors(packet)]
    if errors:
        print("LABEL QUALITY GATE: BLOCKED")
        print("\n".join(f"- {error}" for error in errors))
        raise SystemExit(1)
    print(json.dumps(summarize_packets(packets, difficulties), ensure_ascii=False, indent=2))
