# test_eval.py — 서식 추천/초안 생성 정량 평가
#
# eval_testset.json: 서식을 먼저 정하고 그에 맞춰 쓴 시나리오 32개.
# "이 서식을 목표로 썼다"는 사실 자체가 정답 라벨(target_form)이다 —
# 법률 지식 없이도 라벨링이 가능한 이유는, 정답을 먼저 알고 있는 상태에서
# 거꾸로 질문(시나리오)을 만들었기 때문(정보검색 평가에서 흔히 쓰는 방식).
#
# 측정 지표:
#   1. Top-1 / Top-3 Accuracy — recommend()가 target_form을 1순위/3순위
#      안에 정확히 짚어내는 비율
#   2. 문서 생성 성공률 — draft()가 크래시 없이 파일을 만들어내는 비율
#   3. Field Accuracy(근사치) — extracted에 넣은 이름들이 초안 안에 실제로
#      등장하는 비율 (표 안 내용까지 포함해서 검사)
#
# 실행: python test_eval.py  (ai-api 루트에서)

import json
import sys
import traceback
from pathlib import Path

from app.services.forms.form_recommender import recommend
from app.services.forms.form_drafter import draft, find_hwpx

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "output"


def _flatten_names(extracted: dict) -> list:
    names = []
    for party in extracted.get("당사자", []):
        n = party.get("이름", "")
        if n and n != "미상":
            names.append(n)
    return names


def _draft_contains_names(draft_path: str, names: list) -> tuple:
    """초안(문단+표)에 실제로 등장하는 이름 비율. Field Accuracy 근사치."""
    from hwpx import HwpxDocument
    doc = HwpxDocument.open(draft_path)
    texts = []
    for sec in doc.sections:
        for p in sec.paragraphs:
            texts.append("".join(getattr(r, "text", "") or "" for r in getattr(p, "runs", [])))
    tm = doc.get_table_map()
    for t in tm.get("tables", []):
        for c in t.get("cells", []):
            texts.append(c.get("text", ""))
    full = "\n".join(texts)
    found = [n for n in names if n in full]
    return found, [n for n in names if n not in found]


def main():
    cases = json.loads((ROOT / "eval_testset.json").read_text(encoding="utf-8"))
    print(f"평가 케이스: {len(cases)}개\n")

    results = []
    for i, case in enumerate(cases):
        target = case["target_form"]
        analysis = {
            "case_type": case["case_type"], "case_subtype": case["case_subtype"],
            "summary": case["summary"], "extracted_json": case["extracted_json"],
        }
        row = {"i": i, "target_form": target}
        print(f"[{i+1}/{len(cases)}] 목표: {target}")

        # ── 1. 추천 정확도 ──
        try:
            rec = recommend(analysis)
            recs = [r["form_name"] for r in rec.get("recommendations", [])]
            row["recommendations"] = recs
            row["top1"] = bool(recs) and recs[0] == target
            row["top3"] = target in recs[:3]
            print(f"   추천: {recs}  | Top1={row['top1']} Top3={row['top3']}")
        except Exception as e:
            row["error_recommend"] = f"{type(e).__name__}: {e}"
            row["top1"] = row["top3"] = False
            print(f"   💥 추천 실패: {row['error_recommend']}")
            traceback.print_exc(file=sys.stderr)
            results.append(row)
            continue

        # ── 2. 초안 생성 성공률 + Field Accuracy(근사치) ──
        # 실제 상담원이라면 target_form을 선택했을 것이므로, 추천 성공 여부와
        # 무관하게 target_form 자체로 초안을 만들어 채우기 품질을 잰다.
        if find_hwpx(target) is None:
            row["draft_status"] = "서식파일없음"
            print(f"   ⚠️ 서식 파일을 찾을 수 없음: {target}")
            results.append(row)
            continue

        try:
            d = draft(target, case["extracted_json"], case["summary"])
            if d["error"]:
                row["draft_status"] = "실패"
                row["draft_error"] = d["error"]
                print(f"   ❌ 초안 실패: {d['error']}")
            else:
                row["draft_status"] = "성공"
                names = _flatten_names(case["extracted_json"])
                found, missing = _draft_contains_names(d["file"], names)
                row["field_found"] = found
                row["field_missing"] = missing
                row["field_accuracy"] = len(found) / len(names) if names else None
                row["applied"] = d["applied"]
                row["table_applied"] = d.get("table_applied")
                print(f"   ✅ 초안 성공 (필드 {len(found)}/{len(names)}, "
                      f"applied={d['applied']}, table_applied={d.get('table_applied')})")
        except Exception as e:
            row["draft_status"] = "예외"
            row["draft_error"] = f"{type(e).__name__}: {e}"
            print(f"   💥 초안 예외: {row['draft_error']}")
            traceback.print_exc(file=sys.stderr)

        results.append(row)

    # ── 집계 ──
    n = len(results)
    top1_acc = sum(r.get("top1") for r in results) / n
    top3_acc = sum(r.get("top3") for r in results) / n
    draft_ok = [r for r in results if r.get("draft_status") == "성공"]
    draft_success_rate = len(draft_ok) / n
    field_accs = [r["field_accuracy"] for r in draft_ok if r.get("field_accuracy") is not None]
    avg_field_acc = sum(field_accs) / len(field_accs) if field_accs else None

    print(f"\n{'='*60}")
    print(f"Top-1 Accuracy: {top1_acc:.1%} ({sum(r.get('top1') for r in results)}/{n})")
    print(f"Top-3 Accuracy: {top3_acc:.1%} ({sum(r.get('top3') for r in results)}/{n})")
    print(f"문서 생성 성공률: {draft_success_rate:.1%} ({len(draft_ok)}/{n})")
    if avg_field_acc is not None:
        print(f"평균 Field Accuracy(이름 반영률): {avg_field_acc:.1%}")

    fails = [r for r in results if not r.get("top1")]
    if fails:
        print(f"\n[Top-1 실패 케이스]")
        for r in fails:
            print(f"  목표: {r['target_form']} | 추천: {r.get('recommendations')}")

    out = OUTPUT / "평가결과.json"
    OUTPUT.mkdir(exist_ok=True)
    out.write_text(json.dumps({
        "n": n, "top1_accuracy": top1_acc, "top3_accuracy": top3_acc,
        "draft_success_rate": draft_success_rate, "avg_field_accuracy": avg_field_acc,
        "results": results,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n상세 결과 저장: {out}")


if __name__ == "__main__":
    main()
