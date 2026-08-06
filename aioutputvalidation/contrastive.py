"""Contrastive-learning diagnostics for claim-to-evidence validation."""

from __future__ import annotations

from typing import Sequence

from validator import cosine_similarity


def triplet_margin_loss(
    claim: Sequence[float], positive_evidence: Sequence[float], negative_evidence: Sequence[float], margin: float = 0.20
) -> float:
    """Loss is zero only when the positive is sufficiently closer than the hard negative."""
    if margin < 0:
        raise ValueError("margin must be non-negative")
    return max(0.0, margin - cosine_similarity(claim, positive_evidence) + cosine_similarity(claim, negative_evidence))


def recall_at_k(ranked_evidence_ids: Sequence[Sequence[str]], positive_evidence_ids: Sequence[str], k: int = 3) -> float:
    """Measure how often the correct supporting evidence appears in the top-k results."""
    if len(ranked_evidence_ids) != len(positive_evidence_ids):
        raise ValueError("ranked results and positives must have the same length")
    if k < 1:
        raise ValueError("k must be at least 1")
    if not positive_evidence_ids:
        return 0.0
    hits = sum(positive in ranked[:k] for ranked, positive in zip(ranked_evidence_ids, positive_evidence_ids))
    return round(hits / len(positive_evidence_ids), 4)
