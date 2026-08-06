"""Create label-independent claim/evidence observations before human review."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Callable

from integration import extract_claims, has_uncertainty_disclosure
from fact_conflict import explicit_conflicts, legal_authority_ambiguities, unsupported_assertions
from evidence_diagnostics import rank_claim_evidence
from validator import SUPPORT_THRESHOLD, schema_errors


EmbedMany = Callable[[list[str]], list[list[float]]]


def split_evidence_chunks(transcript: str) -> list[str]:
    """Split source text into sentence-level evidence candidates.

    A whole transcript (or a whole speaker turn) makes every claim compete against
    just one candidate and defeats top-k/hard-negative diagnostics.  Sentence
    boundaries are split only when punctuation is followed by whitespace, which
    avoids breaking dates such as ``2025. 1. 3.``.
    """
    lines = [line.strip() for line in transcript.splitlines() if line.strip() and not line.lstrip().startswith("[")]
    chunks = [sentence.strip() for line in lines for sentence in re.split(r"(?<=[.!?])\s+(?!\d)", line) if sentence.strip()]
    return chunks or ([transcript.strip()] if transcript.strip() else [])


def build_observation(bundle: dict[str, Any], transcript: str, embed_many: EmbedMany, embed_evidence: EmbedMany | None = None) -> dict[str, Any]:
    """Use only generated output and source transcript; no human labels are read."""
    output = bundle["ai_output"]
    claims = extract_claims(output)
    conflicts = explicit_conflicts(claims, transcript)
    assertions = unsupported_assertions(claims, transcript)
    authority_ambiguities = legal_authority_ambiguities(claims, transcript)
    claim_vectors = embed_many(claims) if claims else []
    evidence_chunks = split_evidence_chunks(transcript)
    evidence_vectors = (embed_evidence or embed_many)(evidence_chunks) if evidence_chunks else []
    ranked_scores = [rank_claim_evidence(vector, evidence_vectors) for vector in claim_vectors]
    scores = [float(item["evidence_score"]) for item in ranked_scores]
    errors = schema_errors(output)
    return {
        "case_id": bundle["case_id"],
        "claim_scores": [
            {"claim_id": f"{bundle['case_id']}-C{index:02d}", **diagnostic}
            for index, diagnostic in enumerate(ranked_scores, start=1)
        ],
        "schema_error": int(bool(errors)),
        "schema_error_count": len(errors),
        "schema_error_paths": sorted({error.split(":", 1)[0] for error in errors}),
        "low_support_ratio": round(sum(score < SUPPORT_THRESHOLD for score in scores) / len(scores), 4) if scores else 1.0,
        "citation_missing_ratio": 0.0 if claims else 1.0,
        "uncertainty_disclosed": has_uncertainty_disclosure(claims),
        "explicit_conflicts": conflicts,
        "unsupported_assertions": assertions,
        "legal_authority_ambiguities": authority_ambiguities,
        "evidence_source": "synthetic_transcript_line_chunks_v2",
    }


def e5_embedders(model_name: str) -> tuple[EmbedMany, EmbedMany]:
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError as error:
        raise RuntimeError("sentence-transformers must be installed to build observations") from error
    model = SentenceTransformer(model_name)
    def embed_claims(texts: list[str]) -> list[list[float]]:
        vectors = model.encode([f"query: {text}" for text in texts], normalize_embeddings=True, show_progress_bar=False)
        return vectors.tolist()
    def embed_evidence(texts: list[str]) -> list[list[float]]:
        vectors = model.encode([f"passage: {text}" for text in texts], normalize_embeddings=True, show_progress_bar=False)
        return vectors.tolist()
    return embed_claims, embed_evidence


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build pre-label transcript-grounding observations.")
    parser.add_argument("--model", default="intfloat/multilingual-e5-small")
    parser.add_argument("--catalog", type=Path, default=Path("data/scenario_catalog.json"))
    parser.add_argument("--bundle-dir", type=Path, default=Path("data/03_ai_outputs/generated"))
    parser.add_argument("--output-dir", type=Path, default=Path("data/05_observations"))
    args = parser.parse_args()
    catalog = {item["case_id"]: item for item in json.loads(args.catalog.read_text(encoding="utf-8"))}
    embed_claims, embed_evidence = e5_embedders(args.model)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for path in sorted(args.bundle_dir.glob("SYN-*.json")):
        bundle = json.loads(path.read_text(encoding="utf-8"))
        item = catalog[bundle["case_id"]]
        transcript = (args.catalog.parent / item["transcript_path"]).read_text(encoding="utf-8")
        observation = build_observation(bundle, transcript, embed_claims, embed_evidence)
        target = args.output_dir / path.name
        target.write_text(json.dumps(observation, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"Created {target}")
