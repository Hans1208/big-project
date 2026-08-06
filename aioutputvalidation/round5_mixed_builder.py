"""Create a fresh 15-safe / 15-explicit-conflict mixed validation batch."""

from __future__ import annotations

import json
import shutil
from pathlib import Path


def build(source: Path, destination: Path) -> None:
    catalog = json.loads((source / "catalog.json").read_text(encoding="utf-8"))
    (destination / "ai_outputs").mkdir(parents=True, exist_ok=True); (destination / "transcripts").mkdir(parents=True, exist_ok=True)
    new = []
    for index, item in enumerate(catalog):
        old = item["case_id"]; case_id = old.replace("SYN-R3-", "SYN-R5-")
        bundle = json.loads((source / "ai_outputs" / f"{old}.json").read_text(encoding="utf-8")); bundle["case_id"] = case_id
        if index % 2:
            statement = "법원은 2024-01-15에 이 사건 신청을 기각했고 청구 금액은 98,765,432원으로 확정되었다."
            bundle["ai_output"]["summary"] += " " + statement
            bundle["ai_output"]["timeline_json"].append({"날짜": "2024-01-15", "내용": statement})
        (destination / "ai_outputs" / f"{case_id}.json").write_text(json.dumps(bundle, ensure_ascii=False, indent=2), encoding="utf-8")
        shutil.copyfile(source / "transcripts" / f"{old}.txt", destination / "transcripts" / f"{case_id}.txt")
        new.append({**item, "case_id": case_id, "transcript_path": f"transcripts/{case_id}.txt"})
    (destination / "catalog.json").write_text(json.dumps(new, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    build(Path("data/10_round3"), Path("data/12_round5_mixed")); print("Created 30 mixed validation outputs")
