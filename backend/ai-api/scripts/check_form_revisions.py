"""서식 개정 점검 명령줄 실행 (요구사항 AI-05-04-01).

평소 점검은 관리자 화면(운영 관리 > 서식 개정 모니터링)의 버튼으로 한다.
이 스크립트는 화면 없이 확인하거나 결과를 로그로 남길 때 쓴다.

사용:
    python scripts/check_form_revisions.py            # 점검만
    python scripts/check_form_revisions.py --json     # 결과를 JSON으로 출력

변경이 있으면 종료코드 1, 수집 자체가 실패하면 2로 끝난다.
둘을 구분해야 '변경이 생겼다'와 '점검을 못 했다'를 섞지 않는다.

정기 실행은 아직 걸어두지 않았다. 지금은 각자 PC에서 서버를 띄우는 단계라
어디서 돌릴지가 정해지지 않았고, 켜져 있지 않은 PC에 스케줄을 걸면 점검이
돌았다고 착각하기 쉽다. 배포 환경이 생기면 그때 이 스크립트를 주기 실행에
걸면 된다 - helplaw24는 대부분 2017~2019년에 일괄 등록됐고 그 뒤로는 한 해에
몇 건 수준이라 주 1회로 충분하다(한 번에 22요청).
"""

import io
import json
import sys
from pathlib import Path

# 작업 스케줄러가 돌리면 콘솔 코드페이지가 cp949라 한글 출력이 깨진 채 로그에 남는다.
# 무엇이 바뀌었는지 읽으려고 남기는 로그이므로 여기서 UTF-8로 고정한다.
if hasattr(sys.stdout, "buffer"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.ai.forms import monitor  # noqa: E402


def main() -> int:
    as_json = "--json" in sys.argv
    try:
        result = monitor.check()
    except monitor.FormMonitorError as exc:
        print(f"[실패] {exc}", file=sys.stderr)
        return 2

    if as_json:
        print(json.dumps(result, ensure_ascii=False, indent=1))
        return 1 if result["changes"]["totalChanged"] else 0

    print(f"점검 시각 : {result['checkedAt']}")
    print(f"수집 서식 : {result['totalForms']}건")
    print(f"결과      : {result['message']}")

    changes = result["changes"]
    labels = {"added": "신규", "revised": "개정(파일 교체)", "removed": "삭제",
              "recategorized": "분류변경", "renamed": "이름변경"}
    for key, label in labels.items():
        rows = changes.get(key) or []
        if not rows:
            continue
        print(f"\n[{label}] {len(rows)}건")
        for row in rows[:20]:
            name = row.get("tmpltNm") or row.get("after") or row.get("before") or ""
            print(f"  {row.get('tmpltNo')}  {name}")
        if len(rows) > 20:
            print(f"  ... 외 {len(rows) - 20}건")

    if changes["totalChanged"]:
        print("\n확인 후 관리자 화면에서 '확인 완료'를 눌러야 다음 점검에 다시 뜨지 않습니다.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
