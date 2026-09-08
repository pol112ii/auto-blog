#!/usr/bin/env python3
"""쓸 준비가 됐는지 한 번에 점검한다.

  python doctor.py

무엇이 빠졌는지와 어떻게 채우는지를 알려준다.
아무것도 고치지 않는다. 보기만 한다.
"""

import importlib.util
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from publish_blogger import load_env          # noqa: E402

problems = []


def report(ok, name, detail="", fix=""):
    print(f"  [{'준비됨' if ok else '필요함'}] {name}" + (f"  — {detail}" if detail else ""))
    if not ok and fix:
        problems.append((name, fix))
    return ok


def mask(value):
    if not value:
        return ""
    return value[:6] + "…" + value[-4:] if len(value) > 14 else "채워짐"


def check_python():
    print("\n■ 파이썬")
    report(sys.version_info >= (3, 9), "파이썬 3.9 이상",
           ".".join(map(str, sys.version_info[:3])),
           "파이썬을 3.9 이상으로 올려주세요.")


def check_playwright():
    print("\n■ 브라우저 자동화")
    installed = importlib.util.find_spec("playwright") is not None
    report(installed, "playwright 설치", fix="pip install playwright")
    if not installed:
        return

    if os.environ.get("CHROMIUM_PATH"):
        report(Path(os.environ["CHROMIUM_PATH"]).exists(),
               "CHROMIUM_PATH 의 브라우저", os.environ["CHROMIUM_PATH"],
               "CHROMIUM_PATH 를 실제 실행 파일로 맞춰주세요.")
        return

    # 브라우저를 띄우지 않고 받아둔 폴더만 본다
    home = Path.home()
    roots = [Path(os.environ["PLAYWRIGHT_BROWSERS_PATH"])] if \
        os.environ.get("PLAYWRIGHT_BROWSERS_PATH") else [
            home / ".cache/ms-playwright",
            home / "Library/Caches/ms-playwright",
            home / "AppData/Local/ms-playwright",
        ]
    found = next((r for r in roots if r.exists() and any(r.glob("chromium-*"))), None)
    report(bool(found), "카드 이미지용 크로미움",
           str(found) if found else "", "playwright install chromium")

    # 네이버는 로그인 세션이 든 진짜 크롬을 쓴다
    chrome = shutil.which("chrome") or shutil.which("google-chrome") or (
        Path("C:/Program Files/Google/Chrome/Application/chrome.exe").exists()
        or Path("/Applications/Google Chrome.app").exists())
    report(bool(chrome), "구글 크롬 (네이버 로그인 세션용)",
           fix="크롬을 설치해주세요. 네이버는 로그인된 크롬 프로필을 그대로 씁니다.")


def check_env():
    print("\n■ .env 설정")
    if not (ROOT / ".env").exists():
        report(False, ".env 파일", fix="cp .env.example .env  (그 뒤 값을 채우세요)")
        return
    report(True, ".env 파일")

    env = load_env()
    needed = [
        ("BLOGGER_CLIENT_ID", "구글 클라우드 콘솔에서 발급"),
        ("BLOGGER_CLIENT_SECRET", "구글 클라우드 콘솔에서 발급"),
        ("BLOGGER_REFRESH_TOKEN", "python blogger_auth.py 실행"),
    ]
    for key, fix in needed:
        report(bool(env.get(key)), key, mask(env.get(key, "")), fix)

    has_blog = env.get("BLOGGER_BLOG_URL") or env.get("BLOGGER_BLOG_ID")
    report(bool(has_blog), "블로그스팟 주소 또는 ID",
           env.get("BLOGGER_BLOG_URL", "") or env.get("BLOGGER_BLOG_ID", ""),
           ".env 의 BLOGGER_BLOG_URL 을 채워주세요.")

    report(bool(env.get("NAVER_BLOG_ID")), "NAVER_BLOG_ID",
           env.get("NAVER_BLOG_ID", ""),
           ".env 의 NAVER_BLOG_ID 를 채워주세요.")

    ad = all(env.get(k) for k in ("NAVER_AD_API_KEY", "NAVER_AD_SECRET_KEY",
                                  "NAVER_AD_CUSTOMER_ID"))
    print(f"  [{'준비됨' if ad else '선택'}] 네이버 검색광고 API"
          f"{'' if ad else '  — 없어도 됩니다. 있으면 검색량이 함께 나옵니다'}")


def check_files():
    print("\n■ 파일")
    for name in ("prompts/post_generator.md", "assets/card.html",
                 "keywords.csv", ".claude/commands/newpost.md"):
        report((ROOT / name).exists(), name, fix=f"{name} 이 없습니다. git pull 해보세요.")


def check_git():
    print("\n■ 저장소")
    try:
        out = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT,
                             capture_output=True, text=True).stdout.strip()
        report(True, "git 사용 가능",
               "저장하지 않은 변경 있음" if out else "깨끗함")
    except Exception:
        report(False, "git 사용 가능")

    tracked = subprocess.run(["git", "ls-files", ".env"], cwd=ROOT,
                             capture_output=True, text=True).stdout.strip()
    report(not tracked, ".env 가 git 에 올라가지 않음",
           fix="git rm --cached .env  (비밀값이 저장소에 올라가 있습니다)")


def main():
    print("=" * 52)
    print("  auto-blog 준비 상태 점검")
    print("=" * 52)

    check_python()
    check_playwright()
    check_env()
    check_files()
    check_git()

    print("\n" + "=" * 52)
    if not problems:
        print("\n전부 준비됐습니다.\n")
        print("남은 확인은 하나뿐입니다. 네이버 셀렉터가 맞는지 보려면:")
        print("  python naver_draft.py --blog-id <아이디> --inspect\n")
        return

    print(f"\n{len(problems)}가지가 남았습니다.\n")
    for name, fix in problems:
        print(f"  {name}")
        print(f"      → {fix}\n")


if __name__ == "__main__":
    main()
