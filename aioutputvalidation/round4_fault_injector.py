"""Build 30 fresh, explicit fault-injection outputs for contrastive validation."""

from __future__ import annotations

import json
import shutil
from pathlib import Path


FAULTS = (
    "상대방은 2024-01-15에 모든 사실을 서면으로 인정했다.",
    "정확한 청구 금액은 98,765,432원으로 확정되었다.",
    "법원은 이미 해당 신청을 기각했다.",
)


def build(source_root: Path, destination: Path) -> None:
    catalog = json.loads((source_root / "catalog.json").read_text(encoding="utf-8"))
    output_dir, transcript_dir = destination / "ai_outputs", destination / "transcripts"
    output_dir.mkdir(parents=True, exist_ok=True); transcript_dir.mkdir(parents=True, exist_ok=True)
    new_catalog = []
    for index, item in enumerate(catalog):
        old_id = item["case_id"]
        case_id = old_id.replace("SYN-R3-", "SYN-R4-")
        bundle = json.loads((source_root / "ai_outputs" / f"{old_id}.json").read_text(encoding="utf-8"))
        bundle["case_id"] = case_id
        fault = FAULTS[index % len(FAULTS)]
        bundle["ai_output"]["timeline_json"].append({"날짜": "2024-01-15", "내용": fault})
        bundle["ai_output"]["summary"] += " " + fault
        (output_dir / f"{case_id}.json").write_text(json.dumps(bundle, ensure_ascii=False, indent=2), encoding="utf-8")
        shutil.copyfile(source_root / "transcripts" / f"{old_id}.txt", transcript_dir / f"{case_id}.txt")
        new_catalog.append({**item, "case_id": case_id, "transcript_path": f"transcripts/{case_id}.txt"})
    (destination / "catalog.json").write_text(json.dumps(new_catalog, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    build(Path("data/10_round3"), Path("data/11_round4_faults"))
    print("Created 30 contrastive fault-injection outputs")
