# services/form_embeddings.py — 서식 임베딩 기반 의미 검색
#
# 사전계산: scripts/build_form_embeddings.py 로 MVP 서식명+분류경로를
# text-embedding-3-small로 임베딩해 data/form_embeddings.npy(+index json) 저장.
# 런타임에는 상담 요약/사건개요를 같은 모델로 1회 임베딩해 코사인 유사도로
# 상위 N개 서식을 뽑는다. get_candidates()의 규칙 기반 후보에 합쳐지는
# 보강 소스로만 쓰인다 — 별도 학습 없음(사전학습 임베딩 모델 그대로 사용).

import json
import re
from pathlib import Path

import numpy as np
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
client = OpenAI()

EMBED_MODEL = "text-embedding-3-small"
DATA_DIR = Path(__file__).resolve().parent.parent.parent.parent / "data"
VECTORS_FILE = DATA_DIR / "form_embeddings.npy"
INDEX_FILE = DATA_DIR / "form_embeddings_index.json"

# 서식 hwpx 본문에서 "청구원인/신청원인" 같은 사례 서술 구간만 뽑아
# 임베딩 설명문에 덧붙이기 위한 시작/종료 마커. 공백이 글자 사이에
# 들어간 표기("청  구  원  인")까지 잡도록 글자 사이 \s*를 둔다.
_NARRATIVE_START_RE = re.compile(r"청\s*구\s*원\s*인|신\s*청\s*원\s*인|청\s*구\s*이\s*유|신\s*청\s*이\s*유")
_NARRATIVE_STOP_RE = re.compile(r"첨\s*부\s*서\s*류|첨\s*부\s*자\s*료|위\s*청구인|위\s*신청인|귀\s*중")


def extract_narrative(doc, max_chars: int = 400) -> str:
    """hwpx 문서에서 청구원인/신청원인 구간의 예시 서술을 추출.

    법원 제출용 청구서·신청서 계열에만 이 구간이 있고(신고서 등 시구읍면
    사무소 제출용 서식엔 없음) — 없으면 빈 문자열을 반환해 호출부가
    이름/분류만으로 폴백하게 둔다."""
    texts = []
    for sec in doc.sections:
        for p in sec.paragraphs:
            texts.append("".join(getattr(r, "text", "") or "" for r in getattr(p, "runs", [])))

    start = None
    for i, t in enumerate(texts):
        if _NARRATIVE_START_RE.search(t.replace(" ", "")):
            start = i + 1
            break
    if start is None:
        return ""

    chunk, total = [], 0
    for t in texts[start:]:
        if _NARRATIVE_STOP_RE.search(t.replace(" ", "")):
            break
        t = t.strip()
        if t:
            chunk.append(t)
            total += len(t)
        if total >= max_chars:
            break
    return " ".join(chunk)[:max_chars]

_vectors_cache = None
_index_cache = None


def _load():
    global _vectors_cache, _index_cache
    if _vectors_cache is None:
        if not VECTORS_FILE.exists() or not INDEX_FILE.exists():
            return None, None
        _vectors_cache = np.load(VECTORS_FILE)
        _index_cache = json.loads(INDEX_FILE.read_text(encoding="utf-8"))
    return _vectors_cache, _index_cache


def form_description(m: dict, narrative: str = "") -> str:
    """임베딩 대상 텍스트: 서식명 + 분류 경로 (+ 있으면 청구원인 예시 서술)."""
    base = f"{m['name']} ({m['main']} > {m['sub']})"
    return f"{base}. {narrative}" if narrative else base


def embed_texts(texts: list) -> np.ndarray:
    resp = client.embeddings.create(model=EMBED_MODEL, input=texts)
    vecs = np.array([d.embedding for d in resp.data], dtype=np.float32)
    return vecs / np.linalg.norm(vecs, axis=1, keepdims=True)


def search(query_text: str, top_n: int = 10) -> list:
    """쿼리 텍스트와 가장 유사한 서식 상위 top_n개의 매핑 row를 반환.

    사전계산된 임베딩 캐시가 없으면(빌드 스크립트 미실행) 빈 리스트를 반환한다
    — 규칙 기반 후보 생성만으로도 recommend()가 계속 동작하도록 fail-open."""
    vectors, index = _load()
    if vectors is None or not query_text or not query_text.strip():
        return []
    try:
        q = embed_texts([query_text])[0]
    except Exception:
        return []
    sims = vectors @ q
    top_idx = np.argsort(-sims)[:top_n]
    return [index[i] for i in top_idx]
