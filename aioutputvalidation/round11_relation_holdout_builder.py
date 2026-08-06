"""Create independent relationship-fact holdout cases with new wording."""

from __future__ import annotations

import json
import shutil
from pathlib import Path


def build(source: Path, destination: Path) -> None:
    catalog = json.loads((source / "catalog.json").read_text(encoding="utf-8"))
    (destination / "ai_outputs").mkdir(parents=True, exist_ok=True)
    (destination / "transcripts").mkdir(parents=True, exist_ok=True)
    new_catalog = []
    for index, item in enumerate(catalog):
        old_id = item["case_id"]
        case_id = old_id.replace("SYN-R3-", "SYN-R11-")
        bundle = json.loads((source / "ai_outputs" / f"{old_id}.json").read_text(encoding="utf-8"))
        bundle["case_id"] = case_id
        if index % 2:
            conflict = "상대방의 법정대리인이 내담자를 대신해 화해계약을 체결했다."
            bundle["ai_output"]["summary"] += " " + conflict
            bundle["ai_output"]["extracted_json"]["당사자"].append({"역할": "법정대리인", "이름": "상대방의 법정대리인"})
        (destination / "ai_outputs" / f"{case_id}.json").write_text(json.dumps(bundle, ensure_ascii=False, indent=2), encoding="utf-8")
        shutil.copyfile(source / "transcripts" / f"{old_id}.txt", destination / "transcripts" / f"{case_id}.txt")
        new_catalog.append({**item, "case_id": case_id, "transcript_path": f"transcripts/{case_id}.txt"})
    (destination / "catalog.json").write_text(json.dumps(new_catalog, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    build(Path("data/10_round3"), Path("data/19_round11_relation_holdout"))
    print("Created 30 independent Round 11 relationship outputs")
