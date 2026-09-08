#!/usr/bin/env python3
"""소제목 텍스트를 카드 이미지(800x420 PNG)로 만든다.

사용 예:
    python naver_images.py --keyword "청년도약계좌" \
        --headings headings.txt --out images
    python naver_images.py --keyword "청년도약계좌" \
        --heading "핵심 혜택 및 지원 대상은?" --heading "주의사항 4가지"

headings.txt 는 프롬프트가 뽑아주는 IMAGE_CARDS 를 그대로 저장한 파일이다
(소제목 한 줄에 하나). 결과는 out/card_1.png, card_2.png ... 로 저장된다.
"""

import argparse
import html
import os
import random
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

CARD_HTML = Path(__file__).parent / "assets" / "card.html"

# 실행마다 하나를 골라 쓴다. 같은 글 안의 카드들은 같은 테마를 쓴다.
THEMES = {
    "navy":   {"bg": "linear-gradient(135deg,#1e3a5f,#2d5a8e)",
               "accent": "#FFC107", "sub": "#9fc2e8"},
    "forest": {"bg": "linear-gradient(135deg,#1c3d32,#2f6b53)",
               "accent": "#FFD166", "sub": "#a6d8c2"},
    "plum":   {"bg": "linear-gradient(135deg,#3a2140,#66336b)",
               "accent": "#FFB4A2", "sub": "#d7b6dd"},
    "slate":  {"bg": "linear-gradient(135deg,#23272e,#454c57)",
               "accent": "#7FD1FF", "sub": "#b6bec9"},
}

CARD_W, CARD_H = 800, 420


def build_page_html(keyword: str, heading: str, theme: dict) -> str:
    src = CARD_HTML.read_text(encoding="utf-8")
    for token, value in (
        ("__BG__", theme["bg"]),
        ("__ACCENT__", theme["accent"]),
        ("__SUB__", theme["sub"]),
        ("__KEYWORD__", html.escape(keyword)),
        ("__HEADING__", html.escape(heading)),
    ):
        src = src.replace(token, value)
    return src


def render(keyword, headings, out_dir, theme_name=None, scale=2):
    if not CARD_HTML.exists():
        sys.exit(f"카드 템플릿이 없습니다: {CARD_HTML}")

    name = theme_name or random.choice(list(THEMES))
    if name not in THEMES:
        sys.exit(f"모르는 테마: {name} (가능: {', '.join(THEMES)})")
    theme = THEMES[name]

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []

    # 보통은 playwright 가 받아둔 크로미움을 그대로 쓴다.
    # 브라우저를 따로 깔아 쓰는 환경에서는 CHROMIUM_PATH 로 지정한다.
    launch_kwargs = {}
    chromium_path = os.environ.get("CHROMIUM_PATH")
    if chromium_path:
        launch_kwargs["executable_path"] = chromium_path

    with sync_playwright() as p:
        browser = p.chromium.launch(**launch_kwargs)
        page = browser.new_page(
            viewport={"width": CARD_W, "height": CARD_H},
            device_scale_factor=scale,
        )
        for i, heading in enumerate(headings, 1):
            page.set_content(build_page_html(keyword, heading, theme))
            page.wait_for_selector("html[data-fitted='1']")
            path = out_dir / f"card_{i}.png"
            page.locator("#card").screenshot(path=str(path))
            written.append(path)
        browser.close()

    return name, written


def read_headings(args):
    if args.headings:
        lines = Path(args.headings).read_text(encoding="utf-8").splitlines()
    else:
        lines = args.heading or []
    # IMAGE_CARDS 를 그대로 붙여넣어도 되도록 빈 줄과 머리표는 걷어낸다.
    out = []
    for line in lines:
        line = line.strip().lstrip("▶").strip()
        if line and not line.upper().startswith("IMAGE_CARDS"):
            out.append(line)
    return out


def main():
    ap = argparse.ArgumentParser(description="소제목 카드 이미지 생성")
    ap.add_argument("--keyword", required=True, help="카드 상단에 들어갈 키워드")
    ap.add_argument("--headings", help="소제목이 한 줄에 하나씩 든 텍스트 파일")
    ap.add_argument("--heading", action="append", help="소제목 직접 지정 (반복 가능)")
    ap.add_argument("--out", default="images", help="저장 폴더 (기본: images)")
    ap.add_argument("--theme", help=f"테마 고정 ({', '.join(THEMES)}). 기본은 무작위")
    ap.add_argument("--scale", type=int, default=2, help="해상도 배율 (기본 2배)")
    args = ap.parse_args()

    headings = read_headings(args)
    if not headings:
        sys.exit("소제목이 없습니다. --headings 파일이나 --heading 을 주세요.")

    theme, written = render(args.keyword, headings, args.out, args.theme, args.scale)
    print(f"테마: {theme}")
    for path in written:
        print(path)


if __name__ == "__main__":
    main()
