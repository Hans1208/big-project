# scripts/build_form_embeddings.py
#
# MVP 4개 대분류(친족/상속/가사소송/가족관계등록) 서식명+분류경로+(있으면)
# 청구원인 예시 서술을 text-embedding-3-small로 사전 임베딩해
# data/form_embeddings.npy + data/form_embeddings_index.json 으로 저장한다.
# 청구원인 서술은 hwpx 원본에서 직접 추출한다(제목만으로는 "양육비
# 심판청구서"와 "미성년후견 종료 심판청구" 같은 서식이 임베딩 유사도로
# 잘 구분되지 않아서 도입 — services/form_embeddings.extract_narrative 참고).
# 서식 매핑(helplaw24_서식_카테고리_매핑.json)이나 hwpx 원본이 바뀔 때만
# 재실행하면 된다.
#
# 실행 (ai-api 루트에서): python scripts/build_form_embeddings.py

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import numpy as np
from hwpx import HwpxDocument

from services.form_drafter import find_hwpx
from services.form_embeddings import (
    embed_texts, extract_narrative, form_description,
    DATA_DIR, VECTORS_FILE, INDEX_FILE,
)

MVP_CATEGORIES = {"친족", "상속", "가사소송", "가족관계등록"}
MAPPING_FILE = ROOT / "helplaw24_서식_카테고리_매핑.json"
BATCH_SIZE = 100


def _narrative_for(m: dict) -> str:
    path = find_hwpx(m["name"])
    if path is None:
        return ""
    try:
        doc = HwpxDocument.open(str(path))
        return extract_narrative(doc)
    except Exception:
        return ""


def main():
    mapping = json.loads(MAPPING_FILE.read_text(encoding="utf-8"))
    forms = [m for m in mapping if m["main"] in MVP_CATEGORIES]
    print(f"임베딩 대상: {len(forms)}개")

    texts = []
    narrative_hits = 0
    for i, m in enumerate(forms):
        narrative = _narrative_for(m)
        if narrative:
            narrative_hits += 1
        texts.append(form_description(m, narrative))
        if (i + 1) % 50 == 0:
            print(f"  청구원인 추출 {i + 1}/{len(forms)} (적중 {narrative_hits})")
    print(f"청구원인 추출 완료: {narrative_hits}/{len(forms)}개 서식에서 확보")

    batches = []
    for i in range(0, len(texts), BATCH_SIZE):
        batch = texts[i:i + BATCH_SIZE]
        batches.append(embed_texts(batch))
        print(f"  임베딩 {min(i + BATCH_SIZE, len(texts))}/{len(texts)}")
    vectors = np.vstack(batches)

    DATA_DIR.mkdir(exist_ok=True)
    np.save(VECTORS_FILE, vectors)
    INDEX_FILE.write_text(json.dumps(forms, ensure_ascii=False), encoding="utf-8")
    print(f"저장 완료: {VECTORS_FILE} {vectors.shape}, {INDEX_FILE}")


if __name__ == "__main__":
    main()
