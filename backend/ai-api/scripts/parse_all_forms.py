# scripts/parse_all_forms.py
#
# MVP 4개 대분류(친족/상속/가사소송/가족관계등록) 291개 서식을 python-hwpx로
# 파싱해 parsed/ 아래에 서식별 .md(export_rich_markdown, 문단+표 포함) +
# .json(같은 markdown + 표 셀을 {row,col,text}로 따로 뽑은 것)으로 저장한다.
# 다른 조원이 별도로 만드는 벡터 유사도 recommender(청킹→임베딩→Chroma)의
# 입력 코퍼스로 쓰기 위함 — 이 파일들은 recommend()/draft() 로직과 무관하다.
#
# 실행 (ai-api 루트에서): python scripts/parse_all_forms.py

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from hwpx import HwpxDocument

from app.services.forms.form_drafter import find_hwpx

MVP_CATEGORIES = {"친족", "상속", "가사소송", "가족관계등록"}
MAPPING_FILE = ROOT / "helplaw24_서식_카테고리_매핑.json"
OUT_DIR = ROOT / "parsed"


def _safe_filename(name: str) -> str:
    for ch in '\\/:*?"<>|':
        name = name.replace(ch, "_")
    return name


def parse_one(m: dict) -> dict:
    path = find_hwpx(m["name"])
    if path is None:
        return {"error": "서식 파일 없음"}

    doc = HwpxDocument.open(str(path))
    try:
        md = doc.export_rich_markdown()
    except Exception as e:
        md = "\n".join(
            "".join(getattr(r, "text", "") or "" for r in getattr(p, "runs", []))
            for sec in doc.sections for p in sec.paragraphs
        )

    tm = doc.get_table_map()
    tables = [
        {
            "table_index": t.get("table_index"),
            "cells": [{"row": c.get("row"), "col": c.get("col"), "text": c.get("text")}
                      for c in t.get("cells", [])],
        }
        for t in tm.get("tables", [])
    ]
    return {
        "form_name": m["name"], "main": m["main"], "sub": m["sub"],
        "tmpltNo": m.get("tmpltNo"), "source_file": str(path.relative_to(ROOT)),
        "markdown": md, "tables": tables,
    }


def main():
    mapping = json.loads(MAPPING_FILE.read_text(encoding="utf-8"))
    forms = [m for m in mapping if m["main"] in MVP_CATEGORIES]
    print(f"파싱 대상: {len(forms)}개")

    all_results = []
    ok, fail = 0, []
    for i, m in enumerate(forms):
        result = parse_one(m)
        if "error" in result:
            fail.append({"form_name": m["name"], "error": result["error"]})
            continue

        out_dir = OUT_DIR / result["main"] / result["sub"]
        out_dir.mkdir(parents=True, exist_ok=True)
        fname = _safe_filename(result["form_name"])
        (out_dir / f"{fname}.md").write_text(result["markdown"], encoding="utf-8")
        (out_dir / f"{fname}.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

        all_results.append(result)
        ok += 1
        if (i + 1) % 50 == 0:
            print(f"  {i + 1}/{len(forms)}")

    (OUT_DIR / "전체.json").write_text(
        json.dumps(all_results, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\n완료: 성공 {ok} / 실패 {len(fail)} / 전체 {len(forms)}")
    if fail:
        print("실패 목록:")
        for f in fail:
            print(f"  {f['form_name']}: {f['error']}")
    print(f"저장 위치: {OUT_DIR}/ (대분류/소분류/서식명.md, .json) + {OUT_DIR}/전체.json")


if __name__ == "__main__":
    main()
