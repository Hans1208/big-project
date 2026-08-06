"""Join completed human labels with pre-label observations for MLP training."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from training import FEATURE_NAMES_V2


def build_training_rows(packet: dict[str, Any], observation: dict[str, Any]) -> list[dict[str, Any]]:
    if packet["case_id"] != observation["case_id"]:
        raise ValueError("packet and observation case_id must match")
    if packet.get("labeling_status") != "completed_human_review":
        raise ValueError("only completed human labels may enter training")
    scores = {item["claim_id"]: float(item["evidence_score"]) for item in observation.get("claim_scores", [])}
    rows = []
    for claim in packet["claims"]:
        if not isinstance(claim.get("is_hallucination"), bool):
            raise ValueError("is_hallucination must be a human-completed boolean")
        score = scores.get(claim["claim_id"])
        if score is None:
            raise ValueError(f"missing pre-label observation for {claim['claim_id']}")
        rows.append({
            "case_id": packet["case_id"], "claim_id": claim["claim_id"],
            "features": {"schema_error": observation["schema_error"], "evidence_gap": round(1 - score, 4), "low_support_ratio": observation["low_support_ratio"], "citation_missing_ratio": observation["citation_missing_ratio"], "uncertainty_absent": int(not observation["uncertainty_disclosed"])},
            "is_hallucination": claim["is_hallucination"], "labeler_id": packet["reviewer_id"],
        })
    return rows


def build_v2_training_rows(packet: dict[str, Any], observation: dict[str, Any]) -> list[dict[str, Any]]:
    """Build expanded claim-level features without rewriting historical v1 rows."""
    v1_rows = build_training_rows(packet, observation)
    diagnostics = {item["claim_id"]: item for item in observation.get("claim_scores", [])}
    conflict = int(bool(observation.get("explicit_conflicts")))
    unsupported = int(bool(observation.get("unsupported_assertions")))
    rows = []
    for row in v1_rows:
        detail = diagnostics[row["claim_id"]]
        if "evidence_margin" not in detail:
            raise ValueError("v2 rows require claim-level evidence_margin diagnostics")
        features = dict(row["features"])
        features.update({
            "evidence_ambiguity": round(1 - float(detail["evidence_margin"]), 4),
            "explicit_conflict_present": conflict,
            "unsupported_assertion_present": unsupported,
        })
        if set(features) != set(FEATURE_NAMES_V2):
            raise ValueError("v2 feature contract is incomplete")
        rows.append({**row, "features": features, "feature_contract": "claim_evidence_v2"})
    return rows


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Join only completed human labels with pre-label observations.")
    parser.add_argument("--packet-dir", type=Path, default=Path("data/04_gold_labels/label_packets"))
    parser.add_argument("--observation-dir", type=Path, default=Path("data/05_observations"))
    parser.add_argument("--output", type=Path, default=Path("data/training/training_rows.jsonl"))
    parser.add_argument("--feature-contract", choices=("v1", "v2"), default="v1")
    args = parser.parse_args()
    rows: list[dict[str, Any]] = []
    for packet_path in sorted(args.packet_dir.glob("SYN-*.json")):
        observation_path = args.observation_dir / packet_path.name
        if not observation_path.exists():
            raise SystemExit(f"missing observation: {observation_path}")
        packet = json.loads(packet_path.read_text(encoding="utf-8"))
        observation = json.loads(observation_path.read_text(encoding="utf-8"))
        builder = build_v2_training_rows if args.feature_contract == "v2" else build_training_rows
        rows.extend(builder(packet, observation))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")
    print(json.dumps({"rows": len(rows), "output": str(args.output)}, ensure_ascii=False))
