"""Non-blocking bridge to the sibling aioutputvalidation project; never reads .env."""
from __future__ import annotations
import logging, sys
from functools import lru_cache
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

def _root() -> Path:
    for parent in Path(__file__).resolve().parents:
        candidate=parent/'aioutputvalidation'
        if (candidate/'integration.py').is_file(): return candidate
    raise RuntimeError('aioutputvalidation unavailable')

@lru_cache(maxsize=1)
def _validation_functions():
    root=_root(); sys.path.insert(0,str(root)) if str(root) not in sys.path else None
    from integration import validate_rag_output_with_service
    from audit import build_audit_record
    return validate_rag_output_with_service, build_audit_record

class _E5EmbeddingService:
    """query/passage-prefixed E5 embeddings, matching aioutputvalidation's own e5_embedders."""
    def __init__(self, model: Any) -> None:
        self._model = model
    def embed_query(self, text: str) -> list[float]:
        return self._model.encode([f'query: {text}'], normalize_embeddings=True, show_progress_bar=False)[0].tolist()
    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts: return []
        return self._model.encode([f'passage: {x}' for x in texts], normalize_embeddings=True, show_progress_bar=False).tolist()

@lru_cache(maxsize=1)
def _embedding_service() -> "_E5EmbeddingService":
    from sentence_transformers import SentenceTransformer
    return _E5EmbeddingService(SentenceTransformer('intfloat/multilingual-e5-small'))

def validate_consultation_output(*, analysis_output: dict[str,Any]|None, legal_sources: dict[str,list[dict[str,Any]]]|None = None) -> dict[str,Any]:
    """Validate against RAG-retrieved statutes/precedents, per MODEL_DEFINITION.md section 6
    (validate_rag_output(_with_service) is the documented integration point; claims are checked
    against actual legal_sources content/citation, not against the consultation transcript)."""
    if not isinstance(analysis_output,dict): return {'status':'unavailable','reason':'analysis_output_missing'}
    try:
        validate_rag_output_with_service, build_audit_record = _validation_functions()
        result = validate_rag_output_with_service(
            ai_output=analysis_output,
            legal_sources=legal_sources or {},
            embedding_service=_embedding_service(),
        )
        return {'status':'available',**build_audit_record(result)}
    except Exception as error:
        logger.exception("Output validation bridge failed; continuing without validation.")
        return {'status':'unavailable','reason':type(error).__name__}
