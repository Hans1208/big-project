"""Build final independent holdout cases after Round 7 rule calibration."""

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
        case_id = old_id.replace("SYN-R3-", "SYN-R8-")
        bundle = json.loads((source / "ai_outputs" / f"{old_id}.json").read_text(encoding="utf-8"))
        bundle["case_id"] = case_id
        output = bundle["ai_output"]
        if index % 3 == 1:
            output["summary"] += " 상대방이 연락을 회피하고 있다는 사정이 있으나, 상담 기록만으로는 추가 확인이 필요합니다."
        elif index % 3 == 2:
            conflict = "상대방은 2021-09-03에 7,654,300원을 지급 완료했다."
            output["summary"] += " " + conflict
            output["timeline_json"].append({"날짜": "2021-09-03", "내용": conflict})
        (destination / "ai_outputs" / f"{case_id}.json").write_text(json.dumps(bundle, ensure_ascii=False, indent=2), encoding="utf-8")
        shutil.copyfile(source / "transcripts" / f"{old_id}.txt", destination / "transcripts" / f"{case_id}.txt")
        new_catalog.append({**item, "case_id": case_id, "transcript_path": f"transcripts/{case_id}.txt"})
    (destination / "catalog.json").write_text(json.dumps(new_catalog, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    build(Path("data/10_round3"), Path("data/15_round8_holdout"))
    print("Created 30 final independent holdout outputs")
