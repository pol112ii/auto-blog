#!/usr/bin/env python3
"""naver_draft.py 의 동작을 네이버 접속 없이 점검한다.

가짜 에디터(tests/mock_editor.html)에 실제로 붙여넣기·이미지 업로드·
태그 입력·임시저장을 시키고, 결과가 기대한 대로인지 확인한다.
셀렉터 이름이 맞는지는 여기서 알 수 없다. 그건 --inspect 로 확인한다.

    python tests/run_mock_test.py
"""

import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PASS, FAIL = "통과", "실패"
failures = []


def check(name, ok, detail=""):
    print(f"  [{PASS if ok else FAIL}] {name}" + (f"  — {detail}" if detail else ""))
    if not ok:
        failures.append(name)


def main():
    tmp = Path(tempfile.mkdtemp())
    state = tmp / "state.html"

    cards = sorted((ROOT / "images").glob("card_*.png"))
    if not cards:
        sys.exit("images/card_*.png 가 없습니다. naver_images.py 를 먼저 돌려주세요.")

    print("가짜 에디터로 흐름을 돌립니다...\n")
    proc = subprocess.run([
        sys.executable, str(ROOT / "naver_draft.py"),
        "--target-url", (ROOT / "tests/mock_editor.html").as_uri(),
        "--html", str(ROOT / "tests/sample_A.html"),
        "--title", "[2026년] 청년도약계좌 조건 및 신청 방법 총정리",
        "--images", str(ROOT / "images"),
        "--tags", str(ROOT / "tests/sample_tags.txt"),
        "--profile", str(tmp / "profile"),
        "--headless", "--no-wait", "--dump-frame", str(state),
    ], capture_output=True, text=True)

    if not state.exists():
        print(proc.stdout, proc.stderr)
        sys.exit("에디터 상태를 받지 못했습니다.")

    html = state.read_text(encoding="utf-8")
    body = html[html.index("se-section-text"):html.index("se-image-file-input")]
    log = re.search(r'id="log">(.*?)</div>', html, re.S)
    log = log.group(1) if log else ""

    print("\n결과 확인\n")

    title = re.search(r'se-section-documentTitle">(.*?)</div></div>', html, re.S)
    title = re.sub(r"<[^>]+>", "", title.group(1)).strip() if title else ""
    check("제목이 들어갔다", title.startswith("[2026년] 청년도약계좌"), title)

    # 블록1 → 카드1 → 블록2 → 카드2 → 블록3 → 카드3 → 블록4
    order = []
    for m in re.finditer(r"<h3[^>]*>|\[이미지: (card_\d\.png)\]", body):
        order.append(m.group(1) if m.group(1) else "h3")
    expected = ["card_1.png", "h3", "card_2.png", "h3", "card_3.png", "h3"]
    check("본문과 카드가 번갈아 들어갔다", order == expected,
          " → ".join(order) if order != expected else "")

    check("여백(빈 문단)이 살아 있다", "&nbsp;" in body)
    check("inline style 이 살아 있다", "margin: 0px" in body)
    check("소제목 테두리 스타일이 살아 있다", "border-left: 4px solid" in body)
    check("본문 색이 살아 있다", "rgb(51, 51, 51)" in body)

    typed = re.findall(r"태그 입력: (.+)", log)
    expected_tags = (ROOT / "tests/sample_tags.txt").read_text(encoding="utf-8")
    expected_tags = [t.strip() for t in expected_tags.split(",") if t.strip()]
    check("태그가 하나씩 입력됐다", typed == expected_tags,
          f"{typed} vs {expected_tags}" if typed != expected_tags else f"{len(typed)}개")

    check("작성중 팝업을 취소로 닫았다", "작성중 팝업: 취소" in log)
    check("카드 3장을 모두 올렸다", log.count("이미지 업로드:") == 3, log.count("이미지 업로드:"))
    check("임시저장을 눌렀다", "임시저장 눌림" in log)
    check("발행은 누르지 않았다", "발행 눌림" not in log)

    print()
    if failures:
        print(f"실패 {len(failures)}건: {', '.join(failures)}")
        sys.exit(1)
    print("전부 통과했습니다.")


if __name__ == "__main__":
    main()
