"""Prepare blind second-review packets and measure independent-label agreement."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


SELECTED_CASES = (
    # 10 per difficulty; primary labels are complete, secondary labels remain blind.
    "SYN-E-001", "SYN-E-002", "SYN-E-004", "SYN-E-005", "SYN-E-006", "SYN-E-007", "SYN-E-009", "SYN-E-010", "SYN-E-012", "SYN-E-013",
    "SYN-M-001", "SYN-M-002", "SYN-M-004", "SYN-M-005", "SYN-M-007", "SYN-M-009", "SYN-M-010", "SYN-M-012", "SYN-M-014", "SYN-M-015",
    "SYN-H-001", "SYN-H-003", "SYN-H-005", "SYN-H-006", "SYN-H-007", "SYN-H-008", "SYN-H-010", "SYN-H-011", "SYN-H-012", "SYN-H-014",
)


def build_blind_packet(source: dict) -> dict:
    """Copy only claim text; original labels and rationales must never be exposed."""
    return {
        "case_id": source["case_id"],
        "candidate_output_path": source["candidate_output_path"],
        "answer_generator": source["answer_generator"],
        "reviewer_id": None,
        "reviewer_role": "second_independent_reviewer",
        "claims": [{"claim_id": claim["claim_id"], "text": claim["text"], "is_supported": None, "is_hallucination": None, "evidence_ids": [], "reviewer_rationale": None} for claim in source["claims"]],
        "labeling_status": "pending_human_review",
        "instruction": "Blind second review: do not access the primary review packet or its labels.",
    }


def cohen_kappa(primary: list[bool], second: list[bool]) -> float:
    if len(primary) != len(second) or not primary:
        raise ValueError("same non-empty label sequences required")
    observed = sum(a == b for a, b in zip(primary, second)) / len(primary)
    p_primary = sum(primary) / len(primary)
    p_second = sum(second) / len(second)
    expected = p_primary * p_second + (1 - p_primary) * (1 - p_second)
    return round((observed - expected) / (1 - expected), 4) if expected < 1 else 1.0


def agreement_report(primary_dir: Path, second_dir: Path) -> dict:
    first, second = [], []
    for case_id in SELECTED_CASES:
        primary = json.loads((primary_dir / f"{case_id}.json").read_text(encoding="utf-8"))
        blind = json.loads((second_dir / f"{case_id}.json").read_text(encoding="utf-8"))
        if blind.get("labeling_status") != "completed_human_review" or not blind.get("reviewer_id"):
            raise ValueError(f"{case_id}: second review is incomplete")
        by_id = {claim["claim_id"]: claim for claim in primary["claims"]}
        for claim in blind["claims"]:
            original = by_id.get(claim["claim_id"])
            if not original or not isinstance(claim.get("is_hallucination"), bool):
                raise ValueError(f"{case_id}: invalid claim label")
            first.append(original["is_hallucination"])
            second.append(claim["is_hallucination"])
    agreement = sum(a == b for a, b in zip(first, second)) / len(first)
    return {"cases": len(SELECTED_CASES), "claims": len(first), "agreement": round(agreement, 4), "cohen_kappa": cohen_kappa(first, second)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Prepare or evaluate blind second-review packets.")
    parser.add_argument("action", choices=("prepare", "evaluate"))
    parser.add_argument("--primary-dir", type=Path, default=Path("data/04_gold_labels/label_packets"))
    parser.add_argument("--second-dir", type=Path, default=Path("data/06_second_review/packets"))
    parser.add_argument("--output", type=Path, default=Path("data/metrics/second_review_agreement.json"))
    args = parser.parse_args()
    if args.action == "prepare":
        args.second_dir.mkdir(parents=True, exist_ok=True)
        for case_id in SELECTED_CASES:
            destination = args.second_dir / f"{case_id}.json"
            if destination.exists():
                continue
            source = json.loads((args.primary_dir / f"{case_id}.json").read_text(encoding="utf-8"))
            destination.write_text(json.dumps(build_blind_packet(source), ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Prepared {len(SELECTED_CASES)} blind second-review packets without overwriting existing work")
    else:
        report = agreement_report(args.primary_dir, args.second_dir)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(report, ensure_ascii=False, indent=2))
