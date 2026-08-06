"""Governance checks for synthetic legal-consultation validation datasets."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from typing import Any


DIFFICULTIES = {"easy", "medium", "hard"}
REQUIRED_FIELDS = {"case_id", "difficulty", "scenario_author", "answer_generator", "gold_labeler", "source_type"}


def validate_manifest(records: list[dict[str, Any]], minimum_per_difficulty: int = 1) -> list[str]:
    """Return protocol violations; callers must block evaluation when any exist."""
    errors: list[str] = []
    case_ids: set[str] = set()
    difficulty_counts: Counter[str] = Counter()
    for index, record in enumerate(records, start=1):
        prefix = f"record {index}"
        missing = REQUIRED_FIELDS - record.keys()
        if missing:
            errors.append(f"{prefix}: missing fields {sorted(missing)}")
            continue
        case_id = str(record["case_id"])
        if case_id in case_ids:
            errors.append(f"{prefix}: duplicate case_id {case_id}")
        case_ids.add(case_id)
        difficulty = record["difficulty"]
        if difficulty not in DIFFICULTIES:
            errors.append(f"{prefix}: difficulty must be easy, medium, or hard")
        else:
            difficulty_counts[difficulty] += 1
        roles = [str(record[name]).strip() for name in ("scenario_author", "answer_generator", "gold_labeler")]
        if len(set(roles)) != 3 or not all(roles):
            errors.append(f"{prefix}: scenario author, answer generator, and gold labeler must be three distinct people")
        if record["source_type"] != "synthetic":
            errors.append(f"{prefix}: this protocol currently accepts only source_type='synthetic'")
    for difficulty in sorted(DIFFICULTIES):
        if difficulty_counts[difficulty] < minimum_per_difficulty:
            errors.append(f"dataset: {difficulty} has fewer than {minimum_per_difficulty} cases")
    return errors


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Validate synthetic dataset role separation and difficulty balance.")
    parser.add_argument("manifest", help="Path to the synthetic dataset manifest JSON")
    parser.add_argument("--minimum-per-difficulty", type=int, default=1)
    arguments = parser.parse_args()
    rows = json.loads(open(arguments.manifest, encoding="utf-8").read())
    violations = validate_manifest(rows, arguments.minimum_per_difficulty)
    if violations:
        print("MANIFEST BLOCKED")
        print("\n".join(f"- {violation}" for violation in violations))
        raise SystemExit(1)
    print("MANIFEST PASSED")
