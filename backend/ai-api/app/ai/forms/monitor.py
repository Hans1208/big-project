"""서식 개정 모니터링 (요구사항 AI-05-04-01).

helplaw24에 올라온 서식 목록을 받아와 직전 스냅샷과 비교하고, 바뀐 것이 있으면
관리자에게 알린다. 점검은 관리자가 화면에서 버튼을 누를 때 실행된다 - 정기 실행은
아직 걸어두지 않았다(scripts/check_form_revisions.py 주석 참고).

파일을 자동으로 교체하지는 않는다. 원본이 .hwp라 서식 구조가 바뀌었을 때
조용히 갈아끼우면 파싱과 초안 생성이 어긋난 채로 돌아간다. 무엇이 바뀌었는지
알려주는 데까지만 하고, 실제 교체는 사람이 확인하고 넣는다.

수집 대상 API는 helplaw24 서식 목록 화면이 쓰는 것과 같다:
    GET /api/lwaCtgry/findUseLwaCtgryTmpltList?instNo=I001000000&page=..&size=..
페이지당 100건, 22페이지로 사이트 전량(2,146건)을 받는다.

다만 알림은 우리가 실제로 쓰는 서식으로 좁힌다. 2,146건을 전부 감시하면
쓰지도 않는 서식의 변경까지 올라와서 정작 봐야 할 것이 묻힌다.
대상은 form_embeddings_index.json에 있는 보유 서식(파싱·임베딩까지 끝난 291건)과
그 서식들이 속한 대분류(친족·상속·가사소송·가족관계등록)다.
대분류째로 보는 이유는 그 안에 새 서식이 올라오면 우리도 받아와야 하기 때문이고,
보유 목록을 따로 합치는 이유는 가진 서식이 다른 대분류로 옮겨갔을 때
'삭제'가 아니라 '분류변경'으로 잡히게 하기 위해서다.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

DATA_DIR = Path(__file__).resolve().parents[3] / "data"
SNAPSHOT_FILE = DATA_DIR / "form_snapshot.json"
# 우리가 실제로 보유(파싱·임베딩)한 서식 목록. 감시 범위를 여기서 끌어온다.
OWNED_INDEX_FILE = DATA_DIR / "form_embeddings_index.json"

LIST_API = "https://www.helplaw24.go.kr/api/lwaCtgry/findUseLwaCtgryTmpltList"
LIST_PAGE = "https://www.helplaw24.go.kr/statuteinfo/template/korea/list"
# 대한법률구조공단 서식(instNo). 같은 화면의 '법원 소송안내마당' 쪽은 다른 instNo를 쓴다.
INST_NO = "I001000000"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)
PAGE_SIZE = 100
REQUEST_INTERVAL_SEC = 0.3
MAX_RETRY = 3


class FormMonitorError(RuntimeError):
    """수집 자체가 실패했을 때. '변경 없음'과 구분하려고 따로 둔다."""


# ── 감시 범위 ───────────────────────────────────────────────────────────

def load_scope() -> tuple[set[str], set[str]]:
    """(보유 서식 tmpltNo, 보유 서식이 속한 대분류) 를 돌려준다."""
    if not OWNED_INDEX_FILE.exists():
        raise FormMonitorError(
            f"보유 서식 목록이 없습니다: {OWNED_INDEX_FILE.name}. "
            "scripts/build_form_embeddings.py로 먼저 생성해야 합니다."
        )
    with OWNED_INDEX_FILE.open(encoding="utf-8") as f:
        owned = json.load(f)
    ids = {r["tmpltNo"] for r in owned if r.get("tmpltNo")}
    mains = {r["main"] for r in owned if r.get("main")}
    return ids, mains


def _main_category(row: dict) -> str:
    """'친족 > 후견인' → '친족'."""
    return (row.get("ctgryNm") or "").split(" > ")[0].strip()


def select_scoped(rows: Iterable[dict], owned_ids: set[str], scope_mains: set[str]) -> list[dict]:
    """감시 대상만 남긴다.

    보유 서식(owned_ids)을 대분류 조건과 별개로 항상 포함시킨다. 대분류만으로 거르면
    보유 서식이 다른 대분류로 옮겨갔을 때 목록에서 빠져 '삭제'로 잡힌다.
    """
    return [r for r in rows
            if r.get("tmpltNo") in owned_ids or _main_category(r) in scope_mains]


# ── 수집 ────────────────────────────────────────────────────────────────

def _fetch_page(page: int, timeout: int = 30) -> dict:
    query = urllib.parse.urlencode({
        "instNo": INST_NO,
        "page": page,
        "size": PAGE_SIZE,
        "desc": "",
        "keywordType": "",
        "keyword": "",
        "upCtgryNo": "",
        "ctgryNo": "",
        "ctgryWholYn": "",
    })
    request = urllib.request.Request(
        f"{LIST_API}?{query}",
        headers={"User-Agent": USER_AGENT, "Referer": LIST_PAGE},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _normalize(row: dict) -> dict:
    """비교에 쓰는 필드만 남긴다.

    atchFileDwnldCnt(다운로드 수)는 일부러 뺀다. 서식 내용과 무관하게 계속 늘어나므로
    그대로 비교하면 매주 전 서식이 '변경됨'으로 잡힌다.
    """
    files = row.get("atchFileList") or []
    first = files[0] if files else {}
    return {
        "tmpltNo": row.get("tmpltNo"),
        "tmpltNm": row.get("tmpltNm"),
        "ctgryNm": row.get("ctgryNm"),
        "atchFileId": row.get("atchFileId"),
        "pdfId": first.get("pdfId"),
        "extn": first.get("atchFileExtnNm"),
        "frstRegDt": row.get("frstRegDt"),
    }


def fetch_live() -> list[dict]:
    """서식 목록 전량을 수집한다. 한 페이지라도 끝내 못 받으면 예외."""
    first = _fetch_page(1)
    total_pages = int(first.get("totalPages") or 0)
    total_elements = int(first.get("totalElements") or 0)
    rows = [_normalize(r) for r in first.get("content") or []]

    for page in range(2, total_pages + 1):
        time.sleep(REQUEST_INTERVAL_SEC)
        for attempt in range(1, MAX_RETRY + 1):
            try:
                payload = _fetch_page(page)
                rows.extend(_normalize(r) for r in payload.get("content") or [])
                break
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
                if attempt == MAX_RETRY:
                    raise FormMonitorError(
                        f"서식 목록 {page}페이지를 받지 못했습니다: {exc}"
                    ) from exc
                time.sleep(2 * attempt)

    # 일부만 받아온 상태로 비교하면 못 받은 서식이 전부 '삭제됨'으로 잡힌다.
    # 그 상태로 알림을 보내면 관리자가 2천 건짜리 오탐을 보게 되므로 여기서 끊는다.
    if total_elements and len(rows) != total_elements:
        raise FormMonitorError(
            f"수집 건수가 맞지 않습니다: {len(rows)}건 / 기대 {total_elements}건"
        )
    return rows


# ── 스냅샷 ──────────────────────────────────────────────────────────────

def load_snapshot() -> dict | None:
    if not SNAPSHOT_FILE.exists():
        return None
    with SNAPSHOT_FILE.open(encoding="utf-8") as f:
        return json.load(f)


def save_snapshot(rows: Iterable[dict], site_total: int | None = None) -> dict:
    """감시 대상 서식만 저장한다. 사이트 전량(2,146건)을 담아두면 파일만 커지고,
    비교도 결국 감시 대상 안에서만 하기 때문이다."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    rows = list(rows)
    snapshot = {
        "capturedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": "helplaw24",
        "instNo": INST_NO,
        "scopedForms": len(rows),
        "siteTotalForms": site_total,
        "forms": rows,
    }
    with SNAPSHOT_FILE.open("w", encoding="utf-8") as f:
        json.dump(snapshot, f, ensure_ascii=False, indent=1)
    return snapshot


# ── 비교 ────────────────────────────────────────────────────────────────

def diff(previous: list[dict], current: list[dict]) -> dict:
    """직전 스냅샷과 이번 수집을 비교한다.

    개정(파일 교체) 판단은 pdfId와 atchFileId를 함께 본다. helplaw24 응답에는
    수정일 필드가 없어서 '언제 고쳤는지'로는 알 수 없다. 대신 첨부 식별자가
    2,146건 전부 유일하고 pdfId가 43자 base64url(=32바이트) 형태라 파일이
    바뀌면 값도 바뀔 것으로 본다. 둘 중 하나만 달라져도 개정 후보로 올린다.
    """
    prev_by = {r["tmpltNo"]: r for r in previous if r.get("tmpltNo")}
    curr_by = {r["tmpltNo"]: r for r in current if r.get("tmpltNo")}

    added = [curr_by[no] for no in curr_by.keys() - prev_by.keys()]
    removed = [prev_by[no] for no in prev_by.keys() - curr_by.keys()]

    revised, renamed, recategorized = [], [], []
    for no in curr_by.keys() & prev_by.keys():
        before, after = prev_by[no], curr_by[no]
        if (before.get("pdfId") != after.get("pdfId")
                or before.get("atchFileId") != after.get("atchFileId")):
            revised.append({"tmpltNo": no, "tmpltNm": after.get("tmpltNm"),
                            "ctgryNm": after.get("ctgryNm"),
                            "beforePdfId": before.get("pdfId"),
                            "afterPdfId": after.get("pdfId")})
        if before.get("tmpltNm") != after.get("tmpltNm"):
            renamed.append({"tmpltNo": no, "before": before.get("tmpltNm"),
                            "after": after.get("tmpltNm")})
        if before.get("ctgryNm") != after.get("ctgryNm"):
            recategorized.append({"tmpltNo": no, "tmpltNm": after.get("tmpltNm"),
                                  "before": before.get("ctgryNm"),
                                  "after": after.get("ctgryNm")})

    changes = {
        "added": sorted(added, key=lambda r: r.get("tmpltNo") or ""),
        "removed": sorted(removed, key=lambda r: r.get("tmpltNo") or ""),
        "revised": sorted(revised, key=lambda r: r["tmpltNo"]),
        "renamed": sorted(renamed, key=lambda r: r["tmpltNo"]),
        "recategorized": sorted(recategorized, key=lambda r: r["tmpltNo"]),
    }
    changes["totalChanged"] = sum(len(v) for v in changes.values())
    return changes


def check() -> dict:
    """수집 → 비교. 스냅샷은 건드리지 않는다(확인만 하는 용도).

    기준선이 아직 없으면 이번 수집을 그대로 기준선으로 저장하고 '첫 수집'으로 알린다.
    비교 대상이 없는 상태에서 전 서식을 '신규'로 올리면 알림이 의미가 없다.
    """
    owned_ids, scope_mains = load_scope()
    site_rows = fetch_live()
    current = select_scoped(site_rows, owned_ids, scope_mains)
    snapshot = load_snapshot()

    if snapshot is None:
        saved = save_snapshot(current, site_total=len(site_rows))
        return {
            "checkedAt": saved["capturedAt"],
            "source": "helplaw24",
            "baseline": True,
            "totalForms": len(current),
            "siteTotalForms": len(site_rows),
            "scope": sorted(scope_mains),
            "changes": {"added": [], "removed": [], "revised": [],
                        "renamed": [], "recategorized": [], "totalChanged": 0},
            "message": f"기준 스냅샷을 새로 만들었습니다({len(current)}건). 다음 점검부터 비교합니다.",
        }

    changes = diff(snapshot.get("forms") or [], current)
    if changes["totalChanged"]:
        message = (
            f"변경 {changes['totalChanged']}건 — "
            f"신규 {len(changes['added'])} · 개정 {len(changes['revised'])} · "
            f"삭제 {len(changes['removed'])} · 분류변경 {len(changes['recategorized'])} · "
            f"이름변경 {len(changes['renamed'])}"
        )
    else:
        message = f"변경 없음 (감시 서식 {len(current)}건, 기준 {snapshot.get('capturedAt', '')})"

    return {
        "checkedAt": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": "helplaw24",
        "baseline": False,
        "baselineCapturedAt": snapshot.get("capturedAt"),
        "totalForms": len(current),
        "siteTotalForms": len(site_rows),
        "scope": sorted(scope_mains),
        "changes": changes,
        "message": message,
    }


def acknowledge() -> dict:
    """관리자가 변경 내용을 확인한 뒤 현재 상태를 새 기준선으로 삼는다.

    이걸 하지 않으면 같은 변경이 매주 계속 올라온다. 반대로 자동으로 갱신해버리면
    아무도 못 본 사이에 변경이 묻히므로, 사람이 확인했다는 표시로만 갱신한다.
    """
    owned_ids, scope_mains = load_scope()
    site_rows = fetch_live()
    current = select_scoped(site_rows, owned_ids, scope_mains)
    saved = save_snapshot(current, site_total=len(site_rows))
    return {
        "capturedAt": saved["capturedAt"],
        "totalForms": len(current),
        "message": f"현재 상태를 기준으로 저장했습니다({len(current)}건).",
    }
