"""Adapter between existing RAG response dictionaries and validation.py.

No backend imports are used here: the API layer can inject its embedding function
without exposing secrets or making validation depend on a particular vector store.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

from validator import ValidationResult, validate

EmbeddingFunction = Callable[[list[str]], list[Sequence[float]]]

UNCERTAINTY_CUES = ("확인필요", "확인 필요", "추가 확인", "가능성", "판단하기 어렵", "단정할 수 없")


def extract_claims(ai_output: dict[str, Any]) -> list[str]:
    """Extract auditable factual claim candidates, not new legal conclusions."""
    claims = [str(ai_output.get("summary", "")).strip()]
    extracted = ai_output.get("extracted_json", {})
    if isinstance(extracted, dict):
        claims.append(str(extracted.get("사건개요", "")).strip())
    timeline = ai_output.get("timeline_json", [])
    if isinstance(timeline, list):
        claims.extend(str(item.get("내용", "")).strip() for item in timeline if isinstance(item, dict))
    return list(dict.fromkeys(claim for claim in claims if claim))


def extract_evidence(rag_results: list[dict[str, Any]]) -> tuple[list[str], int]:
    """Use only RAG text returned by the service and count usable citations."""
    texts: list[str] = []
    cited_count = 0
    for result in rag_results:
        content = str(result.get("content", "")).strip()
        citation = str(result.get("citation", "")).strip()
        if content:
            texts.append(content)
            cited_count += int(bool(citation))
    return texts, cited_count


def has_uncertainty_disclosure(claims: list[str]) -> bool:
    """Detect explicit Korean uncertainty language already present in the AI output."""
    return any(cue in claim for claim in claims for cue in UNCERTAINTY_CUES)


def validate_rag_output(
    ai_output: dict[str, Any],
    rag_results: list[dict[str, Any]],
    embed: EmbeddingFunction,
    uncertainty_disclosed: bool | None = None,
) -> ValidationResult:
    """Create embeddings locally through the injected function and validate output."""
    claims = extract_claims(ai_output)
    evidence_texts, usable_citations = extract_evidence(rag_results)
    claim_embeddings = embed(claims) if claims else []
    evidence_embeddings = embed(evidence_texts) if evidence_texts else []
    disclosed = has_uncertainty_disclosure(claims) if uncertainty_disclosed is None else uncertainty_disclosed
    return validate(
        ai_output,
        claim_embeddings,
        evidence_embeddings,
        cited_claim_count=min(len(claims), usable_citations),
        uncertainty_disclosed=disclosed,
    )


def flatten_legal_sources(legal_sources: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    """Flatten the existing related_statutes/related_precedents API shape."""
    return [
        item
        for key in ("related_statutes", "related_precedents")
        for item in legal_sources.get(key, [])
        if isinstance(item, dict)
    ]


def validate_rag_output_with_service(
    ai_output: dict[str, Any],
    legal_sources: dict[str, list[dict[str, Any]]],
    embedding_service: Any,
    uncertainty_disclosed: bool | None = None,
) -> ValidationResult:
    """Adapter for the existing EmbeddingService (query/passages use E5 prefixes)."""
    claims = extract_claims(ai_output)
    evidence_texts, usable_citations = extract_evidence(flatten_legal_sources(legal_sources))
    claim_embeddings = [embedding_service.embed_query(claim) for claim in claims]
    evidence_embeddings = embedding_service.embed_documents(evidence_texts)
    disclosed = has_uncertainty_disclosure(claims) if uncertainty_disclosed is None else uncertainty_disclosed
    return validate(
        ai_output,
        claim_embeddings,
        evidence_embeddings,
        cited_claim_count=min(len(claims), usable_citations),
        uncertainty_disclosed=disclosed,
    )
