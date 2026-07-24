# test_sample.py — 291개 서식 중 무작위 표본을 뽑아 draft→verify 일괄 실행
#
# 목적: "목업 3건에서 되는 게 다른 서식에서도 되는가"를 291개 전수검사 전에
# 저비용으로 먼저 확인한다.
#
# 목업은 대분류(친족/상속/가사소송/가족관계등록)별로 몇 개씩 준비해두고,
# 뽑힌 서식의 실제 카테고리에 맞는 목업을 그 안에서 무작위로 골라 쓴다.
# (고정 3개를 전체 291개에 그냥 순환시키면 "이혼 목업을 상속 서식에 억지로
# 끼워맞추는" 식이 되어 등급이 의미 없어짐 — 카테고리를 맞춰야 verify() 등급이
# 실제 신호를 갖는다.)

import json
import random
import sys
import traceback
from pathlib import Path

from services.form_drafter import draft
from services.form_verifier import verify

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent
HWPX_ROOT = ROOT / "서식_hwpx"

MOCKS_BY_CATEGORY = {
    "친족": [
        {
            # extracted_json 구조를 AI_ANALYSIS 실제 산출물(app/agents/case_analysis)과
            # 동일하게 맞춤: 당사자(배열)/금액/날짜/사건개요.
            "extracted": {
                "당사자": [
                    {"역할": "청구인(양육자, 모)", "이름": "김영희"},
                    {"역할": "상대방(비양육자, 부)", "이름": "이철수"},
                    {"역할": "사건본인(자녀)", "이름": "이수민"},
                ],
                "금액": 3000000,
                "날짜": ["2024-07-10", "2026-01"],
                "사건개요": "2024년 7월 협의이혼 하면서 월 50만원 양육비 지급을 협의했으나, "
                           "상대방이 2026년 1월부터 6개월째 미지급하여 총 300만원이 연체됨. "
                           "3월과 5월 두 차례 문자로 지급을 요청했으나 응답이 없었음. "
                           "상대방은 급여소득자로 소득이 있는 것으로 확인됨.",
            },
            "summary": "2024년 7월 협의이혼 하면서 월 50만원 양육비 지급을 협의했으나, "
                       "상대방이 올해 1월부터 6개월째 미지급. 총 300만원 연체. "
                       "3월과 5월에 문자로 지급을 요청했지만 응답이 없었음. "
                       "상대방은 대한물산 재직 중인 급여소득자로 소득이 있는 것으로 확인됨.",
        },
        {
            "extracted": {
                "당사자": [
                    {"역할": "청구인(처)", "이름": "박지연"},
                    {"역할": "상대방(부)", "이름": "최민호"},
                    {"역할": "사건본인(자녀)", "이름": "최서준"},
                ],
                "금액": 30000000,
                "날짜": ["2016-05-14", "2023", "2026-03-01"],
                "사건개요": "혼인 10년차. 배우자가 2023년경부터 도박을 시작해 가게 운영자금 "
                           "약 1500만원을 잃었고, 그 무렵부터 지속적으로 폭언을 함. "
                           "2026년 3월부터 별거 중이며 이혼과 함께 위자료 3천만원 청구 희망. "
                           "8세 자녀 1명(초등학교 2학년)의 양육권도 원함.",
            },
            "summary": "혼인 10년차. 배우자가 2023년경부터 도박을 시작해 가게 운영자금 "
                       "약 1500만원을 잃었고, 그 무렵부터 지속적으로 폭언을 함. "
                       "올해 3월부터 별거 중이며 이혼과 함께 위자료 3천만원 청구 희망. "
                       "8세 자녀 1명(초등학교 2학년)의 양육권도 원함.",
        },
        {
            "extracted": {
                "당사자": [
                    {"역할": "청구인(모)", "이름": "정수진"},
                    {"역할": "상대방(부, 친권자)", "이름": "강태우"},
                    {"역할": "사건본인(자녀)", "이름": "강하늘"},
                ],
                "금액": None,
                "날짜": ["2017-09-02", "2026-04-15"],
                "사건개요": "이혼 후 친권자인 전 배우자가, 2026년 4월 자녀가 선천성 "
                           "심장질환으로 수술이 필요하다는 진단을 받았음에도 3개월째 "
                           "수술 동의서 서명을 거부해 자녀 복리가 위태로움. 의료행위 "
                           "동의권에 관한 친권만 일부 제한을 구함.",
            },
            "summary": "이혼 후 친권자인 전 배우자가, 올해 4월 자녀가 선천성 심장질환으로 "
                       "수술이 필요하다는 진단을 받았음에도 3개월째 수술 동의서 서명을 "
                       "거부해 자녀 복리가 위태로움. 의료행위에 관한 친권만 일부 제한하고 "
                       "나머지 친권은 유지되길 원함.",
        },
        {
            "extracted": {
                "당사자": [
                    {"역할": "청구인(자녀)", "이름": "윤서연"},
                    {"역할": "사건본인(모)", "이름": "윤말순"},
                ],
                "금액": 80000000,
                "날짜": ["2025-09-10"],
                "사건개요": "고령의 모가 2025년 9월 알츠하이머 진단을 받아 재산관리 "
                           "능력을 상실했음. 예금 8천만원과 아파트(시가 약 4억)를 "
                           "관리할 사람이 필요해 자녀가 성년후견 개시를 청구하려 함. "
                           "다른 형제자매 2명도 후견 개시에 동의한 상태.",
            },
            "summary": "고령의 모가 2025년 9월 ○○병원에서 알츠하이머 진단을 받아 "
                       "재산관리 능력을 상실했음. 예금 8천만원과 아파트(시가 약 4억)를 "
                       "관리할 사람이 필요해 자녀가 성년후견 개시를 청구하려 함. "
                       "다른 형제자매 2명도 후견 개시에 동의한 상태.",
        },
    ],
    "상속": [
        {
            "extracted": {
                "당사자": [
                    {"역할": "청구인(장남)", "이름": "한지훈"},
                    {"역할": "상대방(차녀)", "이름": "한지수"},
                    {"역할": "상대방(삼남)", "이름": "한지민"},
                    {"역할": "피상속인", "이름": "한영수"},
                ],
                "금액": None,
                "날짜": ["2025-11-02", "2025-12-20"],
                "사건개요": "부친이 2025년 11월 사망한 후 공동상속인 3명(장남·차녀·삼남) "
                           "간 상속재산(아파트 시가 약 6억, 예금 5천만원, 차량 1대) 분할을 "
                           "12월에 협의했으나 결렬. 이후 차녀가 협의 없이 단독으로 아파트 "
                           "명의를 이전하려 해 심판을 청구하려 함.",
            },
            "summary": "부친이 2025년 11월 사망한 후 공동상속인 3명(장남·차녀·삼남) 간 "
                       "상속재산(아파트 시가 약 6억, 예금 5천만원, 차량 1대) 분할을 "
                       "12월에 협의했으나 결렬. 이후 차녀가 협의 없이 단독으로 아파트 "
                       "명의를 이전하려 해 심판을 청구하려 함.",
        },
        {
            "extracted": {
                "당사자": [
                    {"역할": "청구인(차남)", "이름": "오민재"},
                    {"역할": "상대방(장녀, 수증자)", "이름": "오은주"},
                    {"역할": "피상속인", "이름": "오태준"},
                ],
                "금액": 45000000,
                "날짜": ["2022-03-10", "2025-08-15"],
                "사건개요": "부친이 2022년 3월 장녀에게만 상가건물(시가 약 3억)을 증여하고 "
                           "2025년 8월 사망. 다른 상속재산이 거의 없어 차남은 상속받은 것이 "
                           "없는 상태. 유류분이 침해되어 유류분반환청구를 하려 하며, "
                           "부족액은 약 4,500만원으로 산정됨.",
            },
            "summary": "부친이 2022년 3월 장녀에게만 상가건물(시가 약 3억)을 증여하고 "
                       "2025년 8월 사망. 다른 상속재산이 거의 없어 차남은 상속받은 것이 "
                       "없는 상태. 유류분이 침해되어 유류분반환청구를 하려 하며, "
                       "부족액은 약 4,500만원으로 산정됨.",
        },
        {
            "extracted": {
                "당사자": [
                    {"역할": "신청인(자녀)", "이름": "서지우"},
                    {"역할": "피상속인", "이름": "서인호"},
                ],
                "금액": None,
                "날짜": ["2026-02-10"],
                "사건개요": "부친이 2026년 2월 사망 직후 상속채무(신용대출·카드빚 약 "
                           "1억 2천만원)가 상속재산(예금 약 3천만원)보다 훨씬 많다는 "
                           "것을 알게 되어 한정승인을 신청하려 함.",
            },
            "summary": "부친이 2026년 2월 사망 직후 상속채무(신용대출·카드빚 약 1억 2천만원)가 "
                       "상속재산(예금 약 3천만원)보다 훨씬 많다는 것을 알게 되어 "
                       "한정승인을 신청하려 함.",
        },
    ],
    "가사소송": [
        {
            "extracted": {
                "당사자": [
                    {"역할": "원고(처)", "이름": "임수현"},
                    {"역할": "피고(부)", "이름": "조현우"},
                ],
                "금액": None,
                "날짜": ["2024-03-05"],
                "사건개요": "2024년 3월 혼인신고는 되어있으나, 신고 이후 단 한 번도 동거한 "
                           "적이 없고 실제 혼인의사 없이 형식적으로만 신고된 것이어서 "
                           "혼인무효확인의 소를 제기하려 함. 각자 다른 주소지에 거주 중인 "
                           "주민등록표등본이 증거.",
            },
            "summary": "2024년 3월 혼인신고는 되어있으나, 신고 이후 단 한 번도 동거한 적이 "
                       "없고 실제 혼인의사 없이 형식적으로만 신고된 것이어서 혼인무효확인의 "
                       "소를 제기하려 함. 각자 다른 주소지에 거주 중인 주민등록표등본이 증거.",
        },
        {
            "extracted": {
                "당사자": [
                    {"역할": "원고(모)", "이름": "배도윤"},
                    {"역할": "피고(법률상 부)", "이름": "배준서"},
                    {"역할": "사건본인(자녀)", "이름": "배하은"},
                ],
                "금액": None,
                "날짜": ["2019-06-01", "2026-05-20"],
                "사건개요": "법률상 부와 자녀 사이에 혈연관계가 없다는 사실이 2026년 5월 "
                           "유전자 검사(친자관계 확률 0%)로 확인되어 친생자관계부존재확인의 "
                           "소를 제기하려 함.",
            },
            "summary": "법률상 부와 자녀 사이에 혈연관계가 없다는 사실이 2026년 5월 "
                       "○○법의학연구소의 유전자 검사(친자관계 확률 0%)로 확인되어 "
                       "친생자관계부존재확인의 소를 제기하려 함.",
        },
        {
            "extracted": {
                "당사자": [
                    {"역할": "원고(양부)", "이름": "노형석"},
                    {"역할": "피고(양자)", "이름": "노시우"},
                ],
                "금액": None,
                "날짜": ["2015-04-20", "2025"],
                "사건개요": "2015년 입양한 양자가 성년이 된 후 2025년부터 지속적으로 "
                           "폭력을 행사했고(3회 이상, 그중 1회는 경찰 출동) 같은 시기부터 "
                           "현재까지 부양(생활비)을 거부하고 있어 파양청구를 하려 함.",
            },
            "summary": "2015년 입양한 양자가 성년이 된 후 2025년부터 지속적으로 폭력을 "
                       "행사했고(3회 이상, 그중 1회는 경찰 출동) 같은 시기부터 현재까지 "
                       "부양(생활비)을 거부하고 있어 파양청구를 하려 함.",
        },
    ],
    "가족관계등록": [
        {
            "extracted": {
                "당사자": [
                    {"역할": "신청인", "이름": "김하람"},
                ],
                "금액": None,
                "날짜": ["2001-05-12"],
                "사건개요": "기존 이름의 발음 때문에 초중고 학창시절 내내 놀림을 받았고, "
                           "최근 직장에서도 같은 일이 반복되어 정신적 스트레스가 심함. "
                           "'김하은'으로 개명허가를 신청하려 함.",
            },
            "summary": "기존 이름의 발음 때문에 초중고 학창시절 내내 놀림을 받았고, "
                       "최근 직장에서도 같은 일이 반복되어 정신적 스트레스가 심함. "
                       "사회생활 지장을 이유로 개명허가를 신청하려 함.",
        },
        {
            "extracted": {
                "당사자": [
                    {"역할": "남편", "이름": "권도현"},
                    {"역할": "아내", "이름": "신유진"},
                ],
                "금액": None,
                "날짜": ["2026-06-01"],
                "사건개요": "2026년 6월 1일 서울 강남구에서 혼인식을 올린 후, "
                           "시구읍면사무소에 혼인신고서를 제출하려 함.",
            },
            "summary": "2026년 6월 1일 서울 강남구에서 혼인식을 올린 후, "
                       "시구읍면사무소에 혼인신고서를 제출하려 함.",
        },
        {
            "extracted": {
                "당사자": [
                    {"역할": "신청인", "이름": "문승우"},
                ],
                "금액": None,
                "날짜": ["2010"],
                "사건개요": "부모가 모두 가족관계등록이 없는 무적자 상태로 2010년경 "
                           "사망하여 본인도 가족관계등록부가 없는 상태. 취업과 건강보험 "
                           "가입에 계속 어려움을 겪고 있어 가족관계등록부를 새로 창설하려 함.",
            },
            "summary": "부모가 모두 가족관계등록이 없는 무적자 상태로 2010년경 사망하여 "
                       "본인도 가족관계등록부가 없는 상태. 취업과 건강보험 가입에 계속 "
                       "어려움을 겪고 있어 가족관계등록부를 새로 창설하려 함.",
        },
    ],
}
# 카테고리 폴더명이 위 키와 정확히 안 맞을 경우를 대비한 fallback
_ALL_MOCKS = [m for mocks in MOCKS_BY_CATEGORY.values() for m in mocks]


def pick_mock(category: str) -> dict:
    pool = MOCKS_BY_CATEGORY.get(category) or _ALL_MOCKS
    return random.choice(pool)


def main():
    sample_size = int(sys.argv[1]) if len(sys.argv) > 1 else 35
    seed = int(sys.argv[2]) if len(sys.argv) > 2 else 42

    all_forms = sorted(HWPX_ROOT.rglob("*.hwpx"))
    print(f"전체 서식: {len(all_forms)}개")

    random.seed(seed)
    sample = random.sample(all_forms, min(sample_size, len(all_forms)))
    print(f"표본: {len(sample)}개 (seed={seed})\n")

    results = []
    for i, path in enumerate(sample):
        category = path.relative_to(HWPX_ROOT).parts[0]
        mock = pick_mock(category)
        row = {
            "form": path.stem, "category": category,
            "path": str(path.relative_to(HWPX_ROOT)),
            "status": None, "grade": None, "error": None,
        }
        print(f"[{i+1}/{len(sample)}] {category} / {path.stem}")
        try:
            d = draft(path.stem, mock["extracted"], mock["summary"])
            if d["error"]:
                row["status"] = "draft_error"
                row["error"] = d["error"]
                print(f"   ❌ 초안 실패: {d['error']}")
            else:
                row["status"] = "ok"
                row["applied"] = d["applied"]
                row["missed"] = len(d["missed"])
                row["rewritten_count"] = d["rewritten_count"]
                row["rewrite_rejected"] = len(d["rewrite_rejected"])
                row["field_generation_error"] = d.get("field_generation_error")
                row["marked_examples"] = d.get("marked_examples")
                row["llm_hallucination"] = d.get("llm_hallucination")
                row["llm_role_swap"] = d.get("llm_role_swap")
                rep = verify(path, d["file"], mock["extracted"])
                row["grade"] = rep["grade"]
                row["hallucinated_dates"] = rep["hallucinated_dates"]
                row["hallucinated_money"] = rep["hallucinated_money"]
                row["example_residue"] = len(rep["example_residue"])
                fld_note = " ⚠️정형치환실패(예시문단만 처리됨)" if d.get("field_generation_error") else ""
                judge_note = ""
                if d.get("llm_hallucination") or d.get("llm_role_swap"):
                    judge_note = (f" ⚠️인명/지명 환각의심:{d.get('llm_hallucination')} "
                                   f"역할바뀜:{d.get('llm_role_swap')}")
                print(f"   ✅ {rep['grade']} (재서술 {d['rewritten_count']}건, "
                      f"환각의심 날짜{len(rep['hallucinated_dates'])}/금액{len(rep['hallucinated_money'])}, "
                      f"예시잔존 {len(rep['example_residue'])}, 안전장치표시 {d.get('marked_examples')}){fld_note}{judge_note}")
        except Exception as e:
            row["status"] = "exception"
            row["error"] = f"{type(e).__name__}: {e}"
            print(f"   💥 예외: {row['error']}")
            traceback.print_exc(file=sys.stderr)
        results.append(row)

    # ── 집계 ──
    ok = [r for r in results if r["status"] == "ok"]
    errors = [r for r in results if r["status"] != "ok"]
    grade_counts = {}
    for r in ok:
        grade_counts[r["grade"]] = grade_counts.get(r["grade"], 0) + 1

    print(f"\n{'='*60}")
    print(f"표본 {len(sample)}개 중 정상 처리 {len(ok)}개 / 오류 {len(errors)}개")
    print(f"등급 분포: {grade_counts}")
    if errors:
        print("\n[오류 목록]")
        for r in errors:
            print(f"  - {r['category']}/{r['form']}: {r['status']} — {r['error']}")

    out = ROOT / "output" / "샘플검증결과.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps({
        "sample_size": len(sample), "seed": seed,
        "ok": len(ok), "errors": len(errors),
        "grade_counts": grade_counts, "results": results,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n상세 결과 저장: {out}")


if __name__ == "__main__":
    main()
