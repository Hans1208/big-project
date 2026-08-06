"""Claim-level evidence ranking diagnostics used by the v2 validation path."""

from __future__ import annotations

from typing import Sequence

from validator import cosine_similarity


def rank_claim_evidence(
    claim: Sequence[float], evidence_vectors: Sequence[Sequence[float]]
) -> dict[str, float | int | None]:
    """Return privacy-safe top evidence diagnostics for one claim.

    The result intentionally contains only scores and the chunk position, never the
    transcript text.  A small top-1/top-2 margin means the retrieved support is
    ambiguous even when the best cosine score alone appears high.
    """
    ranked = sorted(
        ((cosine_similarity(claim, evidence), index) for index, evidence in enumerate(evidence_vectors)),
        reverse=True,
    )
    if not ranked:
        return {"evidence_score": 0.0, "top2_evidence_score": 0.0, "evidence_margin": 0.0, "top_evidence_chunk_index": None, "evidence_candidate_count": 0}
    top1, index = ranked[0]
    top2 = ranked[1][0] if len(ranked) > 1 else 0.0
    return {
        "evidence_score": round(top1, 4),
        "top2_evidence_score": round(top2, 4),
        "evidence_margin": round(max(0.0, top1 - top2), 4) if len(ranked) > 1 else 0.0,
        "top_evidence_chunk_index": index,
        "evidence_candidate_count": len(ranked),
    }
