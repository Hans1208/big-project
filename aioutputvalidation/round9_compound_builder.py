"""Create Round 9 cases to compare the retrained shadow MLP on new wording."""

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
        case_id = old_id.replace("SYN-R3-", "SYN-R9-")
        bundle = json.loads((source / "ai_outputs" / f"{old_id}.json").read_text(encoding="utf-8"))
        bundle["case_id"] = case_id
        output = bundle["ai_output"]
        if index % 3 == 1:
            output["summary"] += " 상대방이 자료 제출을 미루고 있는 상황으로 보이나, 상담 기록만으로는 추가 확인이 필요합니다."
        elif index % 3 == 2:
            conflict = "상대방은 2020-11-02에 조정안을 수락했고 5,432,100원을 모두 지급 완료했다."
            output["summary"] += " " + conflict
            output["timeline_json"].append({"날짜": "2020-11-02", "내용": conflict})
        (destination / "ai_outputs" / f"{case_id}.json").write_text(json.dumps(bundle, ensure_ascii=False, indent=2), encoding="utf-8")
        shutil.copyfile(source / "transcripts" / f"{old_id}.txt", destination / "transcripts" / f"{case_id}.txt")
        new_catalog.append({**item, "case_id": case_id, "transcript_path": f"transcripts/{case_id}.txt"})
    (destination / "catalog.json").write_text(json.dumps(new_catalog, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    build(Path("data/10_round3"), Path("data/17_round9_compound"))
    print("Created 30 Round 9 compound validation outputs")
