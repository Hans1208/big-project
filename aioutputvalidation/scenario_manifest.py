"""Create a role-separated manifest from the prepared synthetic scenario catalog."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def build_role_separated_manifest(catalog: list[dict[str, Any]], members: list[str]) -> list[dict[str, Any]]:
    cleaned = [member.strip() for member in members if member.strip()]
    if len(set(cleaned)) < 3:
        raise ValueError("at least three distinct team members are required")
    unique = list(dict.fromkeys(cleaned))
    records = []
    for index, item in enumerate(catalog):
        roles = [unique[(index + offset) % len(unique)] for offset in range(3)]
        records.append({
            "case_id": item["case_id"], "difficulty": item["difficulty"], "source_type": "synthetic",
            "scenario_author": roles[0], "answer_generator": roles[1], "gold_labeler": roles[2],
            "transcript_path": f"02_transcripts/{item['case_id']}.txt",
            "recording_script_path": item["spec_path"],
            "gold_label_path": f"04_gold_labels/{item['case_id']}.json",
        })
    return records


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Create a role-separated synthetic dataset manifest.")
    parser.add_argument("--members", nargs="+", required=True, help="At least three distinct team member labels")
    parser.add_argument("--output", type=Path, default=Path("data/mock_dataset_manifest.json"))
    parser.add_argument("--catalog", type=Path, default=Path("data/scenario_catalog.json"))
    args = parser.parse_args()
    catalog = json.loads(args.catalog.read_text(encoding="utf-8"))
    manifest = build_role_separated_manifest(catalog, args.members)
    args.output.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Created {len(manifest)} role-separated records: {args.output}")
