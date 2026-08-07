"""구조화 분석 계층의 연락처 취급(app/ai/analysis/service.py) 테스트.

세 가지를 확인한다.
 - 주민등록번호는 어느 경로로도 남지 않는다(저장하지 않기로 한 값이다).
 - 전화번호는 구조화 분석 입력에는 남는다. 서식의 연락처칸에 들어가야 하는 값이라
   여기서 지우면 뽑아낼 값이 입력에 없어진다.
 - 출력 검증에 넘기는 사본에서는 서식용 연락처 키를 뺀다. 검증 스키마가
   extracted_json을 네 키로 못박아 두어서, 그대로 넘기면 모든 분석이 형식 오류가 된다.

네트워크도 LLM도 쓰지 않는다.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.ai.analysis import service as S  # noqa: E402

RRN = "901231-1234567"
PHONE = "010-2345-6789"
ADDR = "경기도 수원시 팔달구 인계로 178 삼성아파트 302동 1104호"


# ── 지우는 범위가 계층마다 다르다 ──

def test_판정계층_입력은_주민번호와_전화번호를_모두_지운다():
    out = S.scrub_sensitive_numbers(f"내담자 {RRN}, 연락처 {PHONE}")
    assert RRN not in out
    assert PHONE not in out


def test_구조화분석_입력은_전화번호를_남긴다():
    # 지우면 extracted_json의 전화번호칸에 넣을 값이 입력에 없어진다.
    out = S.scrub_resident_number(f"내담자 {RRN}, 연락처 {PHONE}")
    assert RRN not in out
    assert PHONE in out


# ── 요약에는 연락처가 남지 않는다 ──
# 요약은 변호사 검토와 구조대상 판단에 함께 쓰인다. 필요 없는 개인정보가 그 경로로
# 퍼지면 안 된다.

def test_요약에서_주소와_전화번호를_지운다():
    extracted = {"주소": ADDR, "전화번호": PHONE}
    summary = f"청구인은 {ADDR}에 거주하며 연락처는 {PHONE}입니다."
    out = S.strip_contact_from_summary(summary, extracted)
    assert ADDR not in out
    assert PHONE not in out


def test_괄호로_덧붙인_연락처는_괄호째_지운다():
    # 값만 지우면 "청구인(  )" 처럼 빈 괄호가 남는다.
    extracted = {"주소": ADDR}
    out = S.strip_contact_from_summary(f"청구인({ADDR})은 상속포기를 원합니다.", extracted)
    assert ADDR not in out
    assert "()" not in out.replace(" ", "")


def test_추출값이_없으면_요약을_건드리지_않는다():
    summary = "청구인은 상속포기를 원합니다."
    assert S.strip_contact_from_summary(summary, None) == summary
    assert S.strip_contact_from_summary(summary, {}) == summary


# ── 출력 검증에 넘기는 사본 ──
# aioutputvalidation/schema/ai_analysis.schema.json이 extracted_json을
# required 4키 + additionalProperties:false로 두고 있어서, 아래 셋을 그대로
# 넘기면 "Additional properties are not allowed"가 난다.

def analysis_output(**extra):
    return {
        "summary": "요약",
        "case_type": "가사소송",
        "extracted_json": {
            "당사자": [{"역할": "채권자", "이름": "강윤서"}],
            "금액": 13600000,
            "날짜": [{"항목": "이혼", "값": "2024-03"}],
            "사건개요": "양육비 미지급",
            **extra,
        },
    }


def test_검증_사본에서_연락처_키를_뺀다():
    out = analysis_output(주소=ADDR, 전화번호=PHONE, 개인정보동의=True)
    clean = S.without_draft_contact(out)

    assert set(clean["extracted_json"]) == {"당사자", "금액", "날짜", "사건개요"}


def test_원본은_그대로_둔다():
    # 동의 화면이 이 값으로 주소·전화칸을 미리 채운다. 원본까지 지우면 안 된다.
    out = analysis_output(주소=ADDR, 전화번호=PHONE, 개인정보동의=True)
    S.without_draft_contact(out)

    assert out["extracted_json"]["주소"] == ADDR
    assert out["extracted_json"]["전화번호"] == PHONE


def test_다른_키와_최상위_필드는_유지한다():
    out = analysis_output(주소=ADDR, 사건번호="2026느단1234")
    clean = S.without_draft_contact(out)

    assert clean["extracted_json"]["사건번호"] == "2026느단1234"
    assert clean["summary"] == "요약"
    assert clean["case_type"] == "가사소송"


def test_뺄_것이_없으면_그대로_돌려준다():
    out = analysis_output()
    assert S.without_draft_contact(out) is out


def test_모양이_다르면_건드리지_않는다():
    assert S.without_draft_contact(None) is None
    assert S.without_draft_contact({"extracted_json": "문자열"}) == {"extracted_json": "문자열"}


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
