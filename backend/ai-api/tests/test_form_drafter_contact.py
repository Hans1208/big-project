"""서식 초안의 주소·전화칸 채우기와 별지 보호(app/ai/forms/drafter.py) 테스트.

전부 순수 함수라 네트워크도 LLM도 쓰지 않는다. 서식 원본(서식_hwpx/)이 있으면
실제 서식으로 한 건 더 검증하고, 없으면 그것만 건너뛴다 — 원본은 용량 때문에
git에 없어서 환경마다 있고 없고가 다르다.

pytest 없이도 돌아간다:
    python tests/test_form_drafter_contact.py
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.ai.forms import drafter as D  # noqa: E402

ADDR = "경기도 수원시 팔달구 인계로 178 삼성아파트 302동 1104호"
PHONE = "010-2345-6789"


def fill_addr(text):
    return D._fill_contact_line(
        text, D.BARE_ADDRESS_PAREN_RE, D.ADDRESS_LABEL_RE, ADDR)


def fill_phone(text):
    return D._fill_contact_line(
        text, D.BARE_PHONE_PAREN_RE, D.PHONE_LABEL_RE, PHONE)


# ── 라벨이 괄호에 싸인 칸 ──
# 양육비 직접지급명령 신청서에서 전화칸이 통째로 안 채워졌다. 라벨 앞의 "("를
# 허용하지 않아 ^\s* 다음에 괄호를 만나고 매칭이 끝나 있었다.

def test_괄호만_있는_주소칸은_통째로_값이_된다():
    # "(주소)"는 라벨이 아니라 자리표시자다. 라벨로 두면 안내문구가 인쇄된다.
    assert fill_addr("          (주소)          ").strip() == ADDR


def test_괄호_안_연락처칸은_괄호를_지키며_채운다():
    assert fill_phone("       (연락처 :                ) ").strip() == (
        f"(연락처 : {PHONE})")


def test_구분자가_낀_전화라벨도_채운다():
    # 정규식 선택지 순서 때문에 "전화"까지만 먹고 멈춰 영영 안 채워지고 있었다.
    assert fill_phone("전화․휴대폰번호:").strip() == f"전화․휴대폰번호: {PHONE}"


def test_라벨이_괄호에_들어가도_닫는_괄호가_살아남는다():
    assert fill_addr("(주소 : ○○시 ○○구)").strip() == f"(주소 : {ADDR})"


# ── 자리표시자 구간 ──

def test_안내_괄호는_남기고_자리표시자만_바꾼다():
    # "(우편번호)"를 지우면 상담원이 우편번호를 따로 적어야 하는 걸 알 수 없다.
    assert fill_addr("주소 ○○시 ○○구 ○○길 ○○(우편번호)").strip() == (
        f"주소 {ADDR}(우편번호)")


def test_자리표시자_사이의_템플릿_글자를_남기지_않는다():
    # 첫 자리표시자부터 줄 끝까지 바꾼다. 마지막 조각까지로 잡으면 "…아파트)"가 남는다.
    out = fill_addr("주소 : ○○시 ○○구 ○○길 ○○번지(○○동, ○○아파트)")
    assert out.strip() == f"주소 : {ADDR}"


def test_라벨과_값이_한_낱말로_붙지_않는다():
    assert fill_addr("주소○○시 ○○구").strip() == f"주소 {ADDR}"


def test_이미_값이_있는_칸은_건드리지_않는다():
    text = "주소 서울특별시 종로구 세종대로 1"
    assert fill_addr(text) == text


# ── A단계 일괄 치환에서 주소·전화 걷어내기 ──
# doc.replace_text_in_runs는 '일치하는 곳을 전부' 바꾼다. 서식의 주소칸은
# 청구인·채무자·회사 것이 모양이 같아서 치환 하나가 세 칸을 다 덮었다.

def test_주소칸_치환은_A단계에서_버린다():
    reps = [{"before": "(주소)", "after": ADDR},
            {"before": "(연락처 :        )", "after": PHONE},
            {"before": "등록기준지 ○○시", "after": "서울시 강남구"}]
    kept, dropped = D._drop_contact_fills(reps, ADDR, PHONE)
    assert kept == []
    assert len(dropped) == 3


def test_이름_날짜_치환은_그대로_둔다():
    reps = [{"before": "청 구 인  ○ ○ ○", "after": "청 구 인  강윤서"},
            {"before": "20○○. ○. ○.", "after": "2026. 6. 18."}]
    kept, dropped = D._drop_contact_fills(reps, ADDR, PHONE)
    assert kept == reps
    assert dropped == []


def test_주소를_잘라_넣은_치환도_버린다():
    # GPT가 주소 앞부분만 다른 칸에 넣는 경우가 있다(◇◇지점 → 경기도 수원시 …).
    reps = [{"before": "◇◇지점", "after": "경기도 수원시 팔달구"}]
    kept, _ = D._drop_contact_fills(reps, ADDR, PHONE)
    assert kept == []


def test_짧게_겹치는_값은_버리지_않는다():
    # "수원"만으로 지우면 "수원가정법원"을 채우는 정상 치환까지 사라진다.
    reps = [{"before": "○○법원", "after": "수원가정법원"}]
    kept, _ = D._drop_contact_fills(reps, ADDR, PHONE)
    assert kept == reps


def test_동의를_안_받아_값이_없어도_주소칸은_막는다():
    # 값이 없으면 A단계가 채우는 주소는 지어낸 것이거나 남의 것이다.
    reps = [{"before": "주소 ○○시", "after": "서울시 강남구 테헤란로 1"}]
    kept, _ = D._drop_contact_fills(reps, "", "")
    assert kept == []


# ── 별지 보호 ──
# 별지는 압류·청구의 대상을 특정하는 법정 문구 자리다. B단계가 예시 사연으로
# 오인해 재서술하면 압류채권목록 문구가 통째로 사라진다.

def test_별지_아래_문단은_구간으로_잡힌다():
    texts = ["신 청 이 유", "청구인은 …하였습니다.", "(별 지)", "압류채권목록",
             "양육비채무자(◇◇지점 근무)가 지급받는 채권으로서 …"]
    assert D._annex_mask(texts) == [False, False, True, True, True]


def test_본문_문장은_별지_구간을_열지_않는다():
    # "별지 목록 기재와 같이"로 시작하는 본문이 구간을 열면 그 뒤가 통째로 빠진다.
    texts = ["별지 목록 기재와 같이 상속재산을 분할하기로 협의하였습니다.",
             "청구인은 …하였습니다."]
    assert D._annex_mask(texts) == [False, False]


def test_별지_표기가_달라도_잡는다():
    for marker in ["별지", "(별 지)", "별지.", "( 별지 )"]:
        assert D._annex_mask([marker, "아무 문단"]) == [True, True], marker


# ── 실제 서식 ──

FORM = (Path(__file__).resolve().parent.parent / "서식_hwpx" / "가사소송"
        / "양육비직접지급명령" / "양육비 직접지급명령 신청서.hwpx")


@pytest.mark.skipif(not FORM.exists(), reason="서식 원본이 없는 환경")
def test_청구인_주소가_채무자_회사_칸으로_번지지_않는다():
    from hwpx.document import HwpxDocument

    doc = HwpxDocument.open(str(FORM))
    filled, texts = D._fill_contact_info(doc, ADDR, PHONE)

    # 채권자 주소 한 칸 + 채권자 연락처 한 칸.
    assert filled == 2, texts
    assert sum(ADDR in t for t in texts) == 1, texts
    assert sum(PHONE in t for t in texts) == 1, texts
    # 채무자·소득세원천징수의무자 칸에는 절대 들어가면 안 된다.
    for t in texts:
        assert "채무자" not in t and "원천징수" not in t, t


@pytest.mark.skipif(not FORM.exists(), reason="서식 원본이 없는 환경")
def test_압류채권목록_문구는_재서술_대상에서_빠진다():
    from hwpx.document import HwpxDocument

    doc = HwpxDocument.open(str(FORM))
    for sec in doc.sections:
        texts = ["".join(getattr(r, "text", "") or "" for r in getattr(p, "runs", []))
                 for p in sec.paragraphs]
        hit = [i for i, t in enumerate(texts) if "양육비채무자(◇◇지점" in t]
        if not hit:
            continue
        i = hit[0]
        # 서술체 + 자리표시자라 별지 마스크가 없으면 예시 블록으로 잡힌다.
        assert D._is_narrative(texts[i])
        assert D._annex_mask(texts)[i], "별지 구간으로 잡히지 않았다"
        return
    pytest.fail("압류채권목록 문단을 찾지 못했다")


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
