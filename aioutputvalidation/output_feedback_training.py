"""Convert completed blind output reviews into label-gated MLP feature rows."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


ROUND_ROOTS = (
    "data/10_round3",
    "data/11_round4_faults",
    "data/12_round5_mixed",
    "data/13_round6_independent",
    "data/14_round7_boundary",
)


def build_row(packet: dict, observation: dict) -> dict:
    if packet["case_id"] != observation["case_id"]:
        raise ValueError("packet and observation case_id must match")
    if packet.get("review_status") != "completed_human_output_review":
        raise ValueError("only completed human output reviews may enter MLP training")
    if packet.get("reviewer_decision") not in {"safe", "review_required", "high_risk"}:
        raise ValueError("reviewer_decision must be a completed output decision")
    scores = observation.get("claim_scores", [])
    evidence_score = sum(float(item["evidence_score"]) for item in scores) / len(scores) if scores else 0.0
    return {
        "case_id": packet["case_id"],
        "features": {
            "schema_error": float(observation["schema_error"]),
            "evidence_gap": round(1 - evidence_score, 4),
            "low_support_ratio": float(observation["low_support_ratio"]),
            "citation_missing_ratio": float(observation["citation_missing_ratio"]),
            "uncertainty_absent": float(not observation["uncertainty_disclosed"]),
        },
        "is_hallucination": packet["reviewer_decision"] != "safe",
        "human_output_decision": packet["reviewer_decision"],
        "labeler_id": packet.get("reviewer_id"),
        "source": "blind_human_output_review",
    }


def build_rows(round_roots: tuple[str, ...] = ROUND_ROOTS) -> list[dict]:
    rows = []
    for root_string in round_roots:
        root = Path(root_string)
        feedback_dir = root / "feedback_packets"
        observation_dir = root / "observations"
        for packet_path in sorted(feedback_dir.glob("SYN-*.json")):
            observation_path = observation_dir / packet_path.name
            if not observation_path.exists():
                raise ValueError(f"missing observation: {observation_path}")
            rows.append(build_row(json.loads(packet_path.read_text(encoding="utf-8")), json.loads(observation_path.read_text(encoding="utf-8"))))
    return rows


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build MLP rows only from completed blind output reviews.")
    parser.add_argument("--output", type=Path, default=Path("data/training/output_feedback_rows_r3_r7.jsonl"))
    args = parser.parse_args()
    rows = build_rows()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")
    print(json.dumps({"rows": len(rows), "output": str(args.output)}, ensure_ascii=False))
