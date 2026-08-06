"""Create a human-readable, label-safe readiness report for the evaluation loop."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path


def build_report(packet_dir: Path, split_path: Path) -> str:
    split = json.loads(split_path.read_text(encoding="utf-8"))
    split_by_case = {case_id: name for name, ids in split["assignments"].items() for case_id in ids}
    totals = Counter()
    completed = Counter()
    pending_claims = Counter()
    positives = Counter()
    total_claims = Counter()
    for path in sorted(packet_dir.glob("SYN-*.json")):
        packet = json.loads(path.read_text(encoding="utf-8"))
        partition = split_by_case.get(packet["case_id"], "unassigned")
        totals[partition] += 1
        if packet.get("labeling_status") == "completed_human_review":
            completed[partition] += 1
        for claim in packet.get("claims", []):
            if isinstance(claim.get("is_hallucination"), bool):
                total_claims[partition] += 1
                positives[partition] += int(claim["is_hallucination"])
            else:
                pending_claims[partition] += 1
    ready = not any(pending_claims.values()) and all(positives[name] > 0 for name in ("validation", "test"))
    rows = ["# AI Output Validation — 현재 상태", "", "|분할|사건|완료 사건|라벨된 주장|환각(True)|미완료 주장|", "|---|---:|---:|---:|---:|---:|"]
    for name in ("train", "validation", "test"):
        rows.append(f"|{name}|{totals[name]}|{completed[name]}|{total_claims[name]}|{positives[name]}|{pending_claims[name]}|")
    rows.extend(["", f"## 평가 상태\n\n- {'평가 가능' if ready else '평가 보류'}", "- 조건: 모든 추가 주장이 라벨 완료되고 Validation과 Test에 환각(True) 사례가 각각 하나 이상 있어야 합니다.", "- 평가 시: Train 학습 → Validation 임계값 선택 → 보지 않은 Test Accuracy·Precision·Recall·F1 기록."])
    return "\n".join(rows) + "\n"


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Write the current label/evaluation readiness report.")
    parser.add_argument("--packet-dir", type=Path, default=Path("data/04_gold_labels/label_packets"))
    parser.add_argument("--split", type=Path, default=Path("data/splits/case_split_v1.json"))
    parser.add_argument("--output", type=Path, default=Path("data/metrics/CURRENT_STATUS.md"))
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(build_report(args.packet_dir, args.split), encoding="utf-8")
    print(args.output)
