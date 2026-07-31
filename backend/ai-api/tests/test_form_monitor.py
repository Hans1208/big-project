"""서식 개정 모니터링(app/ai/forms/monitor.py) 비교·범위 로직 테스트.

네트워크도 데이터 파일도 쓰지 않는다. data/는 gitignore라 환경마다 없을 수 있고,
helplaw24를 실제로 부르면 테스트가 사이트 상태에 따라 흔들린다.

pytest 없이도 돌아간다:
    python tests/test_form_monitor.py
pytest가 있으면 그대로 수집된다:
    pytest tests/test_form_monitor.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.ai.forms import monitor  # noqa: E402

OWNED_IDS = {"A1", "A2", "A3"}
SCOPE_MAINS = {"친족", "상속"}


def form(no, name="서식", ctgry="친족 > 후견인", pdf="PDF", atch="ATCH"):
    return {"tmpltNo": no, "tmpltNm": name, "ctgryNm": ctgry,
            "atchFileId": atch, "pdfId": pdf, "extn": "hwp",
            "frstRegDt": "2017-01-01 00:00:00"}


BASE = [form("A1", "가"), form("A2", "나"), form("A3", "다")]


def test_변경_없으면_아무것도_잡히지_않는다():
    assert monitor.diff(BASE, list(BASE))["totalChanged"] == 0


def test_신규_서식을_잡는다():
    result = monitor.diff(BASE, BASE + [form("A4", "라")])
    assert [r["tmpltNo"] for r in result["added"]] == ["A4"]
    assert result["totalChanged"] == 1


def test_삭제된_서식을_잡는다():
    result = monitor.diff(BASE, BASE[:-1])
    assert [r["tmpltNo"] for r in result["removed"]] == ["A3"]


def test_pdfId가_바뀌면_개정으로_잡는다():
    changed = [form("A1", "가", pdf="NEW"), BASE[1], BASE[2]]
    result = monitor.diff(BASE, changed)
    assert len(result["revised"]) == 1
    assert result["revised"][0]["beforePdfId"] == "PDF"
    assert result["revised"][0]["afterPdfId"] == "NEW"


def test_atchFileId만_바뀌어도_개정으로_잡는다():
    # pdfId가 그대로여도 첨부가 교체됐을 수 있어 둘 다 본다.
    changed = [form("A1", "가", atch="NEW"), BASE[1], BASE[2]]
    assert len(monitor.diff(BASE, changed)["revised"]) == 1


def test_이름_변경을_잡는다():
    changed = [form("A1", "가(개정)"), BASE[1], BASE[2]]
    result = monitor.diff(BASE, changed)
    assert result["renamed"][0]["before"] == "가"
    assert result["renamed"][0]["after"] == "가(개정)"


def test_분류_변경을_잡는다():
    changed = [form("A1", "가", ctgry="상속 > 상속포기"), BASE[1], BASE[2]]
    result = monitor.diff(BASE, changed)
    assert result["recategorized"][0]["after"] == "상속 > 상속포기"


def test_다운로드_수는_비교하지_않는다():
    # 다운로드 수는 서식 내용과 무관하게 계속 늘어난다. 비교에 넣으면 매주 전 서식이
    # '변경됨'으로 잡혀 알림이 무의미해진다.
    raw = {"tmpltNo": "A1", "tmpltNm": "가", "ctgryNm": "친족 > 후견인",
           "atchFileId": "ATCH", "atchFileDwnldCnt": 10,
           "atchFileList": [{"pdfId": "PDF", "atchFileExtnNm": "hwp", "atchFileDwnldCnt": 10}],
           "frstRegDt": "2017-01-01 00:00:00"}
    busier = {**raw, "atchFileDwnldCnt": 999,
              "atchFileList": [{**raw["atchFileList"][0], "atchFileDwnldCnt": 999}]}
    assert monitor._normalize(raw) == monitor._normalize(busier)


def test_범위_밖_대분류는_감시하지_않는다():
    site = [form("A1"), form("X9", ctgry="노동 > 임금")]
    scoped = monitor.select_scoped(site, OWNED_IDS, SCOPE_MAINS)
    assert [r["tmpltNo"] for r in scoped] == ["A1"]


def test_범위_안_신규_서식은_보유하지_않아도_감시한다():
    # 우리 대분류에 새 서식이 올라오면 받아와야 하므로 알림 대상이다.
    site = [form("NEW1", ctgry="상속 > 상속포기")]
    assert len(monitor.select_scoped(site, OWNED_IDS, SCOPE_MAINS)) == 1


def test_보유_서식이_다른_대분류로_옮겨가도_빠지지_않는다():
    # 대분류로만 거르면 목록에서 사라져 '삭제'로 잡힌다. 실제로는 분류변경이다.
    site = [form("A1", ctgry="노동 > 임금")]
    scoped = monitor.select_scoped(site, OWNED_IDS, SCOPE_MAINS)
    assert len(scoped) == 1
    assert monitor.diff(BASE, scoped + BASE[1:])["recategorized"][0]["after"] == "노동 > 임금"


if __name__ == "__main__":
    tests = [(name, fn) for name, fn in sorted(globals().items())
             if name.startswith("test_") and callable(fn)]
    failed = []
    for name, fn in tests:
        try:
            fn()
            print(f"  OK    {name}")
        except AssertionError as exc:
            failed.append(name)
            print(f"  FAIL  {name}  {exc}")
    print(f"\n{len(tests) - len(failed)}/{len(tests)} 통과")
    raise SystemExit(1 if failed else 0)
