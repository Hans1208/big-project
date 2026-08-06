"""Run the trained validation pipeline over generated AI outputs without reading labels."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from training import mlp_probability


def load_runtime_manifest(path: Path) -> dict:
    manifest = json.loads(path.read_text(encoding="utf-8"))
    required = {"model_path", "decision_threshold", "active_model_version", "runtime_mode"}
    if not required <= set(manifest):
        raise ValueError("active model manifest is incomplete")
    return manifest


HIGH_RISK_PROBABILITY_THRESHOLD = 0.15


def validate_observation(observation: dict, model: dict, threshold: float, model_version: str) -> dict:
    """`threshold` is the calibrated safe/review_required boundary (see models/active/manifest.json).

    Round 44-50 diagnostics found a "M그룹" of boundary cases whose learned probability
    (~0.0375-0.0386) was consistently above safe S그룹 cases (~0.031) but this function used
    to ignore the `threshold` argument entirely and compare against a hardcoded 0.12, which sat
    far above both groups. That bug is why every M그룹 case was mis-classified `safe` across
    seven consecutive rounds despite human reviewers flagging all of them `review_required`.
    The threshold argument is now the actual decision boundary; see ROUND51_IMPROVEMENT_REPORT.md.
    """
    scores = observation.get("claim_scores", [])
    evidence_score = sum(float(item["evidence_score"]) for item in scores) / len(scores) if scores else 0.0
    features = {
        "schema_error": float(observation["schema_error"]),
        "evidence_gap": 1 - evidence_score,
        "low_support_ratio": float(observation["low_support_ratio"]),
        "citation_missing_ratio": float(observation["citation_missing_ratio"]),
        "uncertainty_absent": float(not observation["uncertainty_disclosed"]),
    }
    probability = mlp_probability(features, model)
    explicit_conflicts = observation.get("explicit_conflicts", [])
    unsupported = observation.get("unsupported_assertions", [])
    authority_ambiguities = observation.get("legal_authority_ambiguities", [])
    # Explicit source conflicts override learned probability. Learned scores without a
    # conflict require stronger evidence before escalating, reducing false positives.
    if features["schema_error"] or explicit_conflicts or probability >= HIGH_RISK_PROBABILITY_THRESHOLD:
        decision = "high_risk"
    elif unsupported or authority_ambiguities or probability >= threshold or features["low_support_ratio"] >= 0.5:
        decision = "review_required"
    else:
        decision = "safe"
    return {
        "output_validation_version": "1.0",
        "case_id": observation["case_id"],
        "schema_valid": not bool(observation["schema_error"]),
        "schema_error_count": int(observation["schema_error"]),
        "evidence_score": round(evidence_score, 4),
        "low_support_ratio": features["low_support_ratio"],
        "explicit_conflicts": explicit_conflicts,
        "unsupported_assertions": unsupported,
        "legal_authority_ambiguities": authority_ambiguities,
        "claim_evidence_scores": scores,
        "hallucination_probability": round(probability, 4),
        "decision_threshold": round(threshold, 4),
        "decision": decision,
        "model_version": model_version,
        "model_mode": "shadow_evaluation",
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
    }


def write_review_queue(results: list[dict], destination: Path) -> None:
    flagged = [result for result in results if result["decision"] != "safe"]
    rows = ["# AI 출력 검증 — 사람 확인 큐", "", "이 문서는 모델이 `review_required` 또는 `high_risk`로 판정한 출력만 모은 검토 목록입니다.", "", "- 원 전사본과 AI 후보 출력을 확인해 모델 판정이 타당한지 검토합니다.", "- 새로운 정답 라벨 파일을 만들지 말고, 검토 의견은 팀 회의 기록 또는 다음 개선 라운드에 사용합니다.", "", "|사건|판정|환각 위험도|근거 점수|", "|---|---|---:|---:|"]
    for result in sorted(flagged, key=lambda item: (item["decision"], -item["hallucination_probability"])):
        rows.append(f"|{result['case_id']}|{result['decision']}|{result['hallucination_probability']:.2%}|{result['evidence_score']:.2%}|")
    rows.extend(["", "각 사건의 원본은 `../02_transcripts/<사건ID>.txt`, AI 후보는 `../03_ai_outputs/generated/<사건ID>.json`, 상세 검증 결과는 이 폴더의 `<사건ID>.json`입니다."])
    destination.write_text("\n".join(rows) + "\n", encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Validate all generated AI outputs from label-independent observations.")
    parser.add_argument("--observation-dir", type=Path, default=Path("data/05_observations"))
    parser.add_argument("--manifest", type=Path, default=Path("models/active/manifest.json"))
    parser.add_argument("--output-dir", type=Path, default=Path("data/07_validation_results"))
    args = parser.parse_args()
    manifest = load_runtime_manifest(args.manifest)
    model_path = Path(manifest["model_path"])
    model = json.loads(model_path.read_text(encoding="utf-8"))
    args.output_dir.mkdir(parents=True, exist_ok=True)
    decisions = Counter()
    results: list[dict] = []
    for path in sorted(args.observation_dir.glob("SYN-*.json")):
        result = validate_observation(json.loads(path.read_text(encoding="utf-8")), model, float(manifest["decision_threshold"]), manifest["active_model_version"])
        (args.output_dir / path.name).write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        decisions[result["decision"]] += 1
        results.append(result)
    summary = {"validated_outputs": sum(decisions.values()), "decision_counts": dict(decisions), "model_version": manifest["active_model_version"], "mode": "shadow_evaluation"}
    (args.output_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    write_review_queue(results, args.output_dir / "REVIEW_QUEUE.md")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
