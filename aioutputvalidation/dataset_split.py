"""Deterministic, difficulty-aware case split with no claim-level leakage."""

from __future__ import annotations

import json
import random
from collections import defaultdict
from pathlib import Path
from typing import Any


SPLITS = ("train", "validation", "test")
RATIOS = {"train": 0.60, "validation": 0.20, "test": 0.20}


def _stratum_counts(count: int, rotation: tuple[str, str, str]) -> dict[str, int]:
    """Largest-remainder allocation; rotations keep tiny pilot strata balanced."""
    allocated = {name: int(count * RATIOS[name]) for name in SPLITS}
    remaining = count - sum(allocated.values())
    remainders = {name: count * RATIOS[name] - allocated[name] for name in SPLITS}
    for name in sorted(SPLITS, key=lambda split: (-remainders[split], rotation.index(split)))[:remaining]:
        allocated[name] += 1
    return allocated


def build_case_split(catalog: list[dict[str, Any]], seed: int = 42) -> dict[str, Any]:
    """Assign complete cases, not individual claims, to 60/20/20 partitions."""
    by_difficulty: dict[str, list[str]] = defaultdict(list)
    for item in catalog:
        case_id, difficulty = item.get("case_id"), item.get("difficulty")
        if not isinstance(case_id, str) or difficulty not in {"easy", "medium", "hard"}:
            raise ValueError("catalog needs case_id and easy/medium/hard difficulty")
        by_difficulty[difficulty].append(case_id)
    if not by_difficulty:
        raise ValueError("catalog cannot be empty")

    allocations: dict[str, dict[str, int]] = {}
    rotations = (("train", "validation", "test"), ("train", "test", "validation"), ("validation", "test", "train"))
    for index, difficulty in enumerate(sorted(by_difficulty)):
        allocations[difficulty] = _stratum_counts(len(by_difficulty[difficulty]), rotations[index % len(rotations)])

    total = len(catalog)
    targets = _stratum_counts(total, ("train", "validation", "test"))
    current = {split: sum(counts[split] for counts in allocations.values()) for split in SPLITS}
    # Per-stratum rounding can drift on 9/18-case pilots. Move the least disruptive
    # case allocation until global 60/20/20 counts are exact.
    while current != targets:
        source = next(split for split in SPLITS if current[split] > targets[split])
        destination = next(split for split in SPLITS if current[split] < targets[split])
        def penalty(difficulty: str) -> float:
            count = len(by_difficulty[difficulty])
            before = sum((allocations[difficulty][name] - count * RATIOS[name]) ** 2 for name in SPLITS)
            adjusted = dict(allocations[difficulty])
            adjusted[source] -= 1
            adjusted[destination] += 1
            after = sum((adjusted[name] - count * RATIOS[name]) ** 2 for name in SPLITS)
            return after - before
        candidates = [difficulty for difficulty in sorted(allocations) if allocations[difficulty][source] > 0]
        chosen = min(candidates, key=penalty)
        allocations[chosen][source] -= 1
        allocations[chosen][destination] += 1
        current[source] -= 1
        current[destination] += 1

    assignments: dict[str, list[str]] = {name: [] for name in SPLITS}
    for difficulty in sorted(by_difficulty):
        case_ids = sorted(by_difficulty[difficulty])
        random.Random(f"{seed}:{difficulty}").shuffle(case_ids)
        cursor = 0
        for split in SPLITS:
            take = allocations[difficulty][split]
            assignments[split].extend(case_ids[cursor: cursor + take])
            cursor += take
    return {
        "split_version": "case_split_v1",
        "seed": seed,
        "ratios": RATIOS,
        "unit": "case_id",
        "assignments": {name: sorted(ids) for name, ids in assignments.items()},
        "counts": {name: len(ids) for name, ids in assignments.items()},
        "note": "Small pilot sets use difficulty-aware largest-remainder rounding; the target ratio is exact at 45 balanced cases.",
    }


def save_case_split(split: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(split, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Create a fixed case-level 60/20/20 split.")
    parser.add_argument("--catalog", type=Path, default=Path("data/scenario_catalog.json"))
    parser.add_argument("--output", type=Path, default=Path("data/splits/case_split_v1.json"))
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    save_case_split(build_case_split(json.loads(args.catalog.read_text(encoding="utf-8")), args.seed), args.output)
    print(args.output)
