"""Create reproducible, secret-free plans for API candidate-output generation."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from api_mock_generator import GENERATOR_ID


PROMPT_VERSION = "1.0"


def transcript_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_generation_plan(catalog: list[dict[str, Any]], data_root: Path, model: str) -> list[dict[str, str]]:
    return [
        {
            "case_id": item["case_id"],
            "difficulty": item["difficulty"],
            "transcript_path": item["transcript_path"],
            "transcript_sha256": transcript_sha256(data_root / item["transcript_path"]),
            "answer_generator": GENERATOR_ID,
            "model": model,
            "prompt_version": PROMPT_VERSION,
        }
        for item in catalog
    ]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Create a secret-free candidate-output generation plan.")
    parser.add_argument("--model", required=True)
    parser.add_argument("--catalog", type=Path, default=Path("data/scenario_catalog.json"))
    parser.add_argument("--output", type=Path, default=Path("data/03_ai_outputs/generation_plan.json"))
    args = parser.parse_args()
    catalog = json.loads(args.catalog.read_text(encoding="utf-8"))
    plan = build_generation_plan(catalog, args.catalog.parent, args.model)
    args.output.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Created {len(plan)} planned generation records: {args.output}")
