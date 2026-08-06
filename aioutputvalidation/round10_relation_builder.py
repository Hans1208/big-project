"""Build independent person/relationship distortion cases for Round 10."""

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
        case_id = old_id.replace("SYN-R3-", "SYN-R10-")
        bundle = json.loads((source / "ai_outputs" / f"{old_id}.json").read_text(encoding="utf-8"))
        bundle["case_id"] = case_id
        output = bundle["ai_output"]
        if index % 3 == 1:
            output["summary"] += " 상대방이 채무자라는 전제에서 대응 자료를 준비할 필요가 있어 보이나, 상담 기록만으로는 당사자 관계를 추가 확인해야 합니다."
        elif index % 3 == 2:
            conflict = "내담자의 배우자가 상대방을 대리하여 이미 합의서를 작성했다."
            output["summary"] += " " + conflict
            output["extracted_json"]["당사자"].append({"역할": "상대방 대리인", "이름": "내담자의 배우자"})
        (destination / "ai_outputs" / f"{case_id}.json").write_text(json.dumps(bundle, ensure_ascii=False, indent=2), encoding="utf-8")
        shutil.copyfile(source / "transcripts" / f"{old_id}.txt", destination / "transcripts" / f"{case_id}.txt")
        new_catalog.append({**item, "case_id": case_id, "transcript_path": f"transcripts/{case_id}.txt"})
    (destination / "catalog.json").write_text(json.dumps(new_catalog, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    build(Path("data/10_round3"), Path("data/18_round10_relation"))
    print("Created 30 Round 10 relationship validation outputs")
