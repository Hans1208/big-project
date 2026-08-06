"""Build 30 independent boundary cases for safe/review/high-risk calibration."""

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
        case_id = old_id.replace("SYN-R3-", "SYN-R7-")
        bundle = json.loads((source / "ai_outputs" / f"{old_id}.json").read_text(encoding="utf-8"))
        bundle["case_id"] = case_id
        output = bundle["ai_output"]

        group = index % 3
        if group == 1:
            # Deliberately non-specific, unsupported assertion: human reviewers should
            # distinguish this from a faithful output and from a hard fact conflict.
            output["summary"] += " 상대방이 책임을 부인하고 있다는 정황이 있으나, 상담 기록만으로는 추가 확인이 필요합니다."
        elif group == 2:
            conflict = "상대방은 2022-05-14에 책임을 인정했고 9,876,500원을 지급 완료했다."
            output["summary"] += " " + conflict
            output["timeline_json"].append({"날짜": "2022-05-14", "내용": conflict})

        (destination / "ai_outputs" / f"{case_id}.json").write_text(
            json.dumps(bundle, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        shutil.copyfile(source / "transcripts" / f"{old_id}.txt", destination / "transcripts" / f"{case_id}.txt")
        new_catalog.append({**item, "case_id": case_id, "transcript_path": f"transcripts/{case_id}.txt"})

    (destination / "catalog.json").write_text(json.dumps(new_catalog, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    build(Path("data/10_round3"), Path("data/14_round7_boundary"))
    print("Created 30 independent boundary outputs")
