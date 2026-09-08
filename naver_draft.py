#!/usr/bin/env python3
"""[A] 원고를 네이버 블로그에 임시저장한다. 발행은 하지 않는다.

  python naver_draft.py --blog-id myblog --html posts/.../A.html \
      --images images --tags posts/.../NAVER_TAGS.txt

동작 방식:
  CSS margin 은 클립보드를 거치면 사라진다. 그래서 DOM 에 직접 넣지 않고,
  [A] HTML 을 브라우저에 렌더링해 선택·복사한 뒤 에디터에 Ctrl+V 로 붙인다.
  지금 손으로 하시는 CodePen 방식을 그대로 자동화한 것이다.

  본문은 <h3> 앞에서 잘라 블록으로 나누고
  블록1 → 카드1 → 블록2 → 카드2 → 블록3 → 카드3 → 블록4 순서로 넣는다.

주의:
  · 로그인은 하지 않는다. 이미 로그인된 크롬 프로필을 그대로 쓴다.
  · 크롬이 켜져 있으면 프로필이 잠겨 실행되지 않는다. 크롬을 먼저 닫을 것.
  · 마지막은 임시저장까지만. 발행 버튼은 누르지 않는다.
"""

import argparse
import random
import re
import sys
import tempfile
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

from naver_selectors import MAIN_FRAME, SEL, WRITE_URL

# 사람처럼 보이도록 동작 사이에 두는 간격(초)
DELAY = (0.8, 2.4)
LONG_DELAY = (2.0, 4.5)


def pause(span=DELAY):
    time.sleep(random.uniform(*span))


def default_profile_dir():
    """OS 별 크롬 기본 프로필 위치."""
    home = Path.home()
    if sys.platform.startswith("win"):
        return home / "AppData/Local/Google/Chrome/User Data"
    if sys.platform == "darwin":
        return home / "Library/Application Support/Google/Chrome"
    return home / ".config/google-chrome"


# ── HTML 을 블록으로 자르기 ────────────────────────────────────────
def split_blocks(html):
    """<h3> 앞에서 잘라 블록 목록을 만든다.

    각 블록은 원본과 똑같이 렌더링되도록 최상위 컨테이너로 다시 감싼다.
    """
    m = re.search(r"<div\b[^>]*>", html)
    if not m:
        return [html]

    opening = m.group(0)
    inner = html[m.end():]
    close = inner.rfind("</div>")
    if close != -1:
        inner = inner[:close]

    parts = [p for p in re.split(r"(?=<h3\b)", inner) if p.strip()]
    return [f"{opening}{p}</div>" for p in parts]


# ── 클립보드 복사 ──────────────────────────────────────────────────
def copy_rendered(page, block_html, tmpdir, index):
    """블록을 파일로 저장해 렌더링한 뒤 전체 선택·복사한다."""
    path = Path(tmpdir) / f"block_{index}.html"
    path.write_text(
        "<!doctype html><meta charset='utf-8'>" + block_html, encoding="utf-8"
    )
    page.goto(path.as_uri())
    page.wait_for_load_state("load")
    pause()
    page.keyboard.press("Control+A")
    pause()
    page.keyboard.press("Control+C")
    pause()


# ── 셀렉터 도우미 ──────────────────────────────────────────────────
def find(frame, key, timeout=8000):
    """후보 중 실제로 보이는 첫 번째 요소를 돌려준다. 없으면 None."""
    for selector in SEL[key]:
        loc = frame.locator(selector).first
        try:
            loc.wait_for(state="visible", timeout=timeout // len(SEL[key]))
            return loc
        except Exception:
            continue
    return None


def dismiss(frame, key):
    """팝업이 떠 있으면 닫는다. 없으면 조용히 지나간다."""
    for selector in SEL[key]:
        loc = frame.locator(selector).first
        try:
            if loc.is_visible(timeout=1200):
                loc.click()
                pause()
                return True
        except Exception:
            continue
    return False


# ── 점검 모드 ──────────────────────────────────────────────────────
def inspect(frame):
    print("\n등록된 셀렉터 후보를 하나씩 확인합니다.\n")
    for key, candidates in SEL.items():
        print(f"[{key}]")
        for selector in candidates:
            try:
                count = frame.locator(selector).count()
                visible = frame.locator(selector).first.is_visible(timeout=800) \
                    if count else False
            except Exception:
                count, visible = 0, False
            mark = "찾음" if visible else ("있으나 안 보임" if count else "없음")
            print(f"   {mark:14} {selector}   (개수 {count})")
        print()
    print("'찾음' 이 하나도 없는 항목은 naver_selectors.py 를 고쳐야 합니다.")


# ── 본작업 ─────────────────────────────────────────────────────────
def run(args):
    html = Path(args.html).read_text(encoding="utf-8")
    blocks = split_blocks(html)

    cards = sorted(Path(args.images).glob("card_*.png")) if args.images else []
    tags = ""
    if args.tags and Path(args.tags).exists():
        tags = Path(args.tags).read_text(encoding="utf-8").strip()

    print(f"본문 블록 {len(blocks)}개, 카드 이미지 {len(cards)}장")

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=str(args.profile),
            channel="chrome",
            headless=False,           # 사람이 보는 앞에서 돌린다
            args=[f"--profile-directory={args.profile_name}"],
            no_viewport=True,
        )
        context.grant_permissions(["clipboard-read", "clipboard-write"],
                                  origin="https://blog.naver.com")

        editor = context.pages[0] if context.pages else context.new_page()
        editor.goto(WRITE_URL.format(blog_id=args.blog_id))
        editor.wait_for_load_state("networkidle")
        pause(LONG_DELAY)

        frame = editor.frame_locator(MAIN_FRAME)

        # "작성 중인 글이 있습니다" → 이어쓰지 않고 새 글로 간다
        dismiss(frame, "popup_continue_cancel")

        if args.inspect:
            inspect(frame)
            input("\n확인이 끝나면 Enter 를 누르세요. 브라우저를 닫습니다.")
            context.close()
            return

        # 제목
        title = find(frame, "title")
        if not title:
            sys.exit("제목 입력란을 찾지 못했습니다. --inspect 로 셀렉터를 확인해주세요.")
        title.click()
        pause()
        editor.keyboard.type(args.title, delay=random.randint(30, 70))
        pause(LONG_DELAY)

        # 본문으로 커서 이동
        body = find(frame, "body")
        if not body:
            sys.exit("본문 입력란을 찾지 못했습니다. --inspect 로 셀렉터를 확인해주세요.")
        body.click()
        pause()

        # 복사 전용 탭. 에디터 탭은 그대로 두고 여기서만 렌더링·복사한다.
        clipper = context.new_page()

        with tempfile.TemporaryDirectory() as tmpdir:
            for i, block in enumerate(blocks):
                copy_rendered(clipper, block, tmpdir, i + 1)

                editor.bring_to_front()
                pause()
                editor.keyboard.press("Control+V")
                pause(LONG_DELAY)
                dismiss(frame, "popup_keep_format")     # 서식 유지 팝업
                editor.keyboard.press("End")
                editor.keyboard.press("Enter")
                pause()

                # 블록 뒤에 카드 이미지 한 장 (마지막 블록 뒤에는 넣지 않는다)
                if i < len(cards) and i < len(blocks) - 1:
                    upload = frame.locator(SEL["image_input"][0]).first
                    for selector in SEL["image_input"]:
                        loc = frame.locator(selector).first
                        if loc.count():
                            upload = loc
                            break
                    upload.set_input_files(str(cards[i]))
                    print(f"  카드 {i + 1} 업로드: {cards[i].name}")
                    pause(LONG_DELAY)
                    editor.keyboard.press("End")
                    editor.keyboard.press("Enter")
                    pause()

        clipper.close()
        editor.bring_to_front()

        # 태그
        if tags:
            tag_box = find(frame, "tag_input", timeout=4000)
            if tag_box:
                tag_box.click()
                pause()
                for tag in [t.strip() for t in tags.split(",") if t.strip()]:
                    editor.keyboard.type(tag, delay=random.randint(40, 90))
                    editor.keyboard.press("Enter")
                    pause()
            else:
                print("태그 입력란을 찾지 못해 건너뜁니다. 직접 넣어주세요.")

        # 임시저장. 여기까지만 한다.
        save = find(frame, "save_draft")
        if not save:
            print("\n임시저장 버튼을 찾지 못했습니다. 브라우저에서 직접 눌러주세요.")
        else:
            save.click()
            pause(LONG_DELAY)
            dismiss(frame, "popup_confirm")
            print("\n임시저장 완료.")

        print("발행은 하지 않았습니다. 확인 후 직접 발행해주세요.")
        input("Enter 를 누르면 브라우저를 닫습니다.")
        context.close()


def main():
    ap = argparse.ArgumentParser(description="네이버 블로그 임시저장 (발행 안 함)")
    ap.add_argument("--blog-id", required=True, help="네이버 블로그 아이디")
    ap.add_argument("--html", help="[A] 원고 HTML 파일")
    ap.add_argument("--title", help="글 제목")
    ap.add_argument("--images", help="카드 이미지 폴더 (card_1.png ...)")
    ap.add_argument("--tags", help="NAVER_TAGS 가 든 파일 (쉼표 구분)")
    ap.add_argument("--profile", type=Path, default=default_profile_dir(),
                    help="크롬 User Data 폴더")
    ap.add_argument("--profile-name", default="Default",
                    help="프로필 이름 (기본: Default)")
    ap.add_argument("--inspect", action="store_true",
                    help="셀렉터가 맞는지만 확인하고 끝낸다")
    args = ap.parse_args()

    if not args.inspect:
        missing = [n for n, v in (("--html", args.html), ("--title", args.title)) if not v]
        if missing:
            ap.error(f"다음 값이 필요합니다: {', '.join(missing)}")

    run(args)


if __name__ == "__main__":
    main()
