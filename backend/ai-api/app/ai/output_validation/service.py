"""Non-blocking bridge to the sibling aioutputvalidation project; never reads .env."""
from __future__ import annotations
import json, sys
from functools import lru_cache
from pathlib import Path
from typing import Any

def _root() -> Path:
    for parent in Path(__file__).resolve().parents:
        candidate=parent/'aioutputvalidation'
        if (candidate/'output_validation_runner.py').is_file(): return candidate
    raise RuntimeError('aioutputvalidation unavailable')

@lru_cache(maxsize=1)
def _runtime(root_text: str):
    root=Path(root_text); sys.path.insert(0,str(root)) if str(root) not in sys.path else None
    from observation_builder import build_observation
    from output_validation_runner import load_runtime_manifest, validate_observation
    manifest=load_runtime_manifest(root/'models/active/manifest.json'); model=json.loads((root/manifest['model_path']).read_text(encoding='utf-8'))
    return build_observation, validate_observation, manifest, model

@lru_cache(maxsize=1)
def _model():
    from sentence_transformers import SentenceTransformer
    return SentenceTransformer('intfloat/multilingual-e5-small')

def validate_consultation_output(*, analysis_output: dict[str,Any]|None, consultation_text: str) -> dict[str,Any]:
    if not isinstance(analysis_output,dict) or not consultation_text.strip(): return {'status':'unavailable','reason':'analysis_output_or_consultation_text_missing'}
    try:
        model=_model(); q=lambda xs:model.encode([f'query: {x}' for x in xs],normalize_embeddings=True,show_progress_bar=False).tolist(); e=lambda xs:model.encode([f'passage: {x}' for x in xs],normalize_embeddings=True,show_progress_bar=False).tolist()
        build, validate, manifest, weights=_runtime(str(_root())); obs=build({'case_id':'runtime-consultation','ai_output':analysis_output},consultation_text,q,e)
        return {'status':'available',**validate(obs,weights,float(manifest['decision_threshold']),manifest['active_model_version'])}
    except Exception as error: return {'status':'unavailable','reason':type(error).__name__}
