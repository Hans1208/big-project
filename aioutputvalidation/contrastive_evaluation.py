"""Evaluate E5 claim-to-evidence rankings against completed human selections."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Callable, Sequence

from contrastive_label_packet import validate_completed_packet
from observation_builder import e5_embedders
from validator import cosine_similarity


EmbedMany = Callable[[list[str]], list[Sequence[float]]]


def evaluate_packets(packets: list[dict], embed_claims: EmbedMany, embed_evidence: EmbedMany) -> dict:
    """Measure retrieval only against independent human contrastive labels."""
    supported = []
    hard_negative_margins = []
    unsupported_top_scores = []
    for packet in packets:
        validate_completed_packet(packet)
        chunks = packet["evidence_chunks"]
        evidence_ids = [item["evidence_id"] for item in chunks]
        evidence_vectors = embed_evidence([item["text"] for item in chunks])
        by_id = dict(zip(evidence_ids, evidence_vectors))
        claims = packet["claims"]
        claim_vectors = embed_claims([item["text"] for item in claims])
        for claim, vector in zip(claims, claim_vectors):
            ranked = sorted(((cosine_similarity(vector, evidence), evidence_id) for evidence_id, evidence in by_id.items()), reverse=True)
            ranked_ids = [evidence_id for _, evidence_id in ranked]
            if claim["support_status"] == "unsupported":
                unsupported_top_scores.append(ranked[0][0] if ranked else 0.0)
                continue
            positives = claim.get("supporting_evidence_ids") or [claim["supporting_evidence_id"]]
            rank = min(ranked_ids.index(positive) + 1 for positive in positives)
            supported.append(rank)
            negative = claim.get("hard_negative_evidence_id")
            if negative:
                hard_negative_margins.append(max(cosine_similarity(vector, by_id[positive]) for positive in positives) - cosine_similarity(vector, by_id[negative]))
    if not supported:
        raise ValueError("at least one supported claim is required")
    return {
        "completed_packets": len(packets),
        "supported_claims": len(supported),
        "unsupported_claims": len(unsupported_top_scores),
        "recall_at_1": round(sum(rank <= 1 for rank in supported) / len(supported), 4),
        "recall_at_3": round(sum(rank <= 3 for rank in supported) / len(supported), 4),
        "mean_reciprocal_rank": round(sum(1 / rank for rank in supported) / len(supported), 4),
        "hard_negative_pairs": len(hard_negative_margins),
        "hard_negative_win_rate": round(sum(margin > 0 for margin in hard_negative_margins) / len(hard_negative_margins), 4) if hard_negative_margins else None,
        "hard_negative_mean_margin": round(sum(hard_negative_margins) / len(hard_negative_margins), 4) if hard_negative_margins else None,
        "unsupported_mean_top_score": round(sum(unsupported_top_scores) / len(unsupported_top_scores), 4) if unsupported_top_scores else None,
    }


def attach_multi_positive_labels(packets: list[dict], clarification_packets: list[dict]) -> list[dict]:
    """Attach independently reviewed multi-positive evidence IDs to Round 61 packets."""
    from multi_evidence_label_packet import validate_completed_packet as validate_multi_positive

    clarification_by_case = {packet["case_id"]: packet for packet in clarification_packets}
    merged = []
    for packet in packets:
        clarification = clarification_by_case.get(packet["case_id"])
        if clarification is None:
            raise ValueError(f"missing multi-positive clarification for {packet['case_id']}")
        validate_multi_positive(clarification)
        positives = {claim["claim_id"]: claim["supporting_evidence_ids"] for claim in clarification["claims"]}
        copied = {**packet, "claims": [{**claim, **({"supporting_evidence_ids": positives[claim["claim_id"]]} if claim.get("support_status") == "supported" else {})} for claim in packet["claims"]]}
        merged.append(copied)
    return merged


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Evaluate completed human contrastive labels with E5 retrieval rankings.")
    parser.add_argument("--packet-dir", type=Path, default=Path("data/61_contrastive_diagnostic/label_packets"))
    parser.add_argument("--model", default="intfloat/multilingual-e5-small")
    parser.add_argument("--output", type=Path, default=Path("data/61_contrastive_diagnostic/contrastive_evaluation.json"))
    parser.add_argument("--multi-positive-dir", type=Path)
    args = parser.parse_args()
    packets = [json.loads(path.read_text(encoding="utf-8")) for path in sorted(args.packet_dir.glob("SYN-*.json"))]
    if args.multi_positive_dir:
        clarification = [json.loads(path.read_text(encoding="utf-8")) for path in sorted(args.multi_positive_dir.glob("SYN-*.json"))]
        packets = attach_multi_positive_labels(packets, clarification)
    claims_embedder, evidence_embedder = e5_embedders(args.model)
    report = evaluate_packets(packets, claims_embedder, evidence_embedder)
    report.update({"embedding_model": args.model, "label_source": "independent_human_multi_positive_review" if args.multi_positive_dir else "independent_human_contrastive_review"})
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
