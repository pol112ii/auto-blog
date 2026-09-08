#!/usr/bin/env python3
"""글 한 편을 만드는 단계들을 나눠 실행한다.

원고 작성은 Claude Code 가 직접 한다. 여기서는 기계가 할 일만 맡는다.
각 단계는 결과를 파일로 남기고, 이미 끝난 단계는 건너뛴다.
그래서 중간에 실패하면 그 단계부터 다시 돌리면 된다.

  python pipeline.py next                 다음에 쓸 키워드를 고른다
  python pipeline.py init <키워드>         작업 폴더를 만든다
  python pipeline.py status <폴더>         어디까지 됐는지 본다
  python pipeline.py publish <폴더>        [B] 발행 → 주소를 [A] 에 심는다
  python pipeline.py cards <폴더>          소제목 카드 이미지를 만든다
  python pipeline.py naver <폴더>          네이버에 임시저장한다
  python pipeline.py done <폴더>           keywords.csv 에 결과를 적는다

  --force 를 붙이면 이미 끝난 단계도 다시 한다.
"""

import argparse
import csv
import datetime as dt
import json
import re
import subprocess
import sys
from pathlib import Path

from publish_blogger import load_env

ROOT = Path(__file__).resolve().parent
KEYWORDS = ROOT / "keywords.csv"
POSTS = ROOT / "posts"
FIELDS = ["keyword", "official_url", "extra_urls", "status",
          "google_url", "naver_done", "date", "naver_blog_id"]

# 작업 폴더 안에 놓이는 파일들
A_HTML = "A.html"
B_HTML = "B.html"
TAGS = "NAVER_TAGS.txt"
CARDS = "IMAGE_CARDS.txt"
META = "meta.json"
IMAGES = "images"


# ── keywords.csv ───────────────────────────────────────────────────
def read_rows():
    if not KEYWORDS.exists():
        return []
    with KEYWORDS.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_rows(rows):
    with KEYWORDS.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        for row in rows:
            w.writerow({k: row.get(k, "") for k in FIELDS})


def find_row(rows, keyword):
    for row in rows:
        if row.get("keyword", "").strip() == keyword:
            return row
    return None


# ── 작업 폴더 ──────────────────────────────────────────────────────
def slugify(keyword):
    slug = re.sub(r"\s+", "-", keyword.strip())
    return re.sub(r"[^\w가-힣-]", "", slug)


def meta_path(folder):
    return Path(folder) / META


def load_meta(folder):
    path = meta_path(folder)
    if not path.exists():
        sys.exit(f"{META} 이 없습니다: {folder}\ninit 부터 다시 해주세요.")
    return json.loads(path.read_text(encoding="utf-8"))


def save_meta(folder, meta):
    meta_path(folder).write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")


def run(cmd, capture=False):
    print("   $ " + " ".join(str(c) for c in cmd))
    result = subprocess.run(cmd, cwd=ROOT, text=True,
                            stdout=subprocess.PIPE if capture else None)
    if result.returncode != 0:
        sys.exit(f"\n실패했습니다 (종료 코드 {result.returncode}). "
                 f"고친 뒤 이 단계만 다시 돌리면 됩니다.")
    return (result.stdout or "").strip()


# ── 단계들 ─────────────────────────────────────────────────────────
def cmd_next(args):
    """status 가 비어 있는 첫 줄을 고른다. 이미 처리된 키워드는 건너뛴다."""
    for row in read_rows():
        if not row.get("status", "").strip():
            print(json.dumps({k: row.get(k, "") for k in FIELDS},
                             ensure_ascii=False))
            return
    sys.exit("처리할 키워드가 없습니다. keywords.csv 를 채워주세요.")


def cmd_init(args):
    rows = read_rows()
    row = find_row(rows, args.keyword)
    if row is None:
        sys.exit(f"keywords.csv 에 없는 키워드입니다: {args.keyword}")
    if row.get("status", "").strip() and not args.force:
        sys.exit(f"이미 처리된 키워드입니다 (status={row['status']}). "
                 f"다시 하려면 --force 를 붙이세요.")

    today = dt.date.today().isoformat()
    folder = POSTS / f"{today}-{slugify(args.keyword)}"
    (folder / IMAGES).mkdir(parents=True, exist_ok=True)

    if not meta_path(folder).exists() or args.force:
        save_meta(folder, {
            "keyword": args.keyword,
            "official_url": row.get("official_url", ""),
            "extra_urls": row.get("extra_urls", ""),
            "naver_blog_id": row.get("naver_blog_id", "").strip(),
            "google_url": "",
            "title": "",
            "today": today,
        })
    print(folder)


def cmd_status(args):
    folder = Path(args.folder)
    meta = load_meta(folder)
    checks = [
        ("[B] 원고", (folder / B_HTML).exists()),
        ("[A] 원고", (folder / A_HTML).exists()),
        ("제목", bool(meta.get("title"))),
        ("태그", (folder / TAGS).exists()),
        ("소제목 목록", (folder / CARDS).exists()),
        ("블로그스팟 발행", bool(meta.get("google_url"))),
        ("[A] 주소 치환", (folder / A_HTML).exists()
            and "{{GOOGLE_URL}}" not in (folder / A_HTML).read_text(encoding="utf-8")),
        ("카드 이미지", any((folder / IMAGES).glob("card_*.png"))),
        ("네이버 임시저장", bool(meta.get("naver_done"))),
    ]
    print(f"\n{folder}\n")
    for name, ok in checks:
        print(f"  [{'끝남' if ok else '아직'}] {name}")
    if meta.get("google_url"):
        print(f"\n  블로그스팟: {meta['google_url']}")
    if meta.get("naver_blog_id"):
        print(f"  네이버 블로그: {meta['naver_blog_id']}")
    print()


def cmd_publish(args):
    folder = Path(args.folder)
    meta = load_meta(folder)
    if meta.get("google_url") and not args.force:
        print(f"이미 발행됐습니다: {meta['google_url']}")
        return

    b = folder / B_HTML
    if not b.exists():
        sys.exit(f"{B_HTML} 이 없습니다. 원고를 먼저 써주세요.")

    print("[B] 를 블로그스팟에 발행합니다.")
    cmd = [sys.executable, "publish_blogger.py", str(b)]
    if meta.get("title"):
        cmd += ["--title", meta["title"]]
    if args.labels:
        cmd += ["--labels", args.labels]
    url = run(cmd, capture=True).splitlines()[-1].strip()
    if not url.startswith("http"):
        sys.exit(f"글 주소를 받지 못했습니다: {url!r}")

    meta["google_url"] = url
    save_meta(folder, meta)

    # [A] 의 자리표시자를 실제 주소로 바꾼다
    a = folder / A_HTML
    if a.exists():
        text = a.read_text(encoding="utf-8")
        if "{{GOOGLE_URL}}" in text:
            a.write_text(text.replace("{{GOOGLE_URL}}", url), encoding="utf-8")
            print(f"[A] 의 {{{{GOOGLE_URL}}}} 를 바꿨습니다.")
    print(url)


def cmd_cards(args):
    folder = Path(args.folder)
    meta = load_meta(folder)
    out = folder / IMAGES
    if any(out.glob("card_*.png")) and not args.force:
        print("카드 이미지가 이미 있습니다.")
        return

    cards = folder / CARDS
    if not cards.exists():
        sys.exit(f"{CARDS} 가 없습니다. IMAGE_CARDS 를 저장해주세요.")

    run([sys.executable, "naver_images.py",
         "--keyword", meta["keyword"],
         "--headings", str(cards),
         "--out", str(out)])


def cmd_naver(args):
    folder = Path(args.folder)
    meta = load_meta(folder)
    if meta.get("naver_done") and not args.force:
        print("이미 임시저장했습니다.")
        return

    a = folder / A_HTML
    if not a.exists():
        sys.exit(f"{A_HTML} 이 없습니다.")
    text = a.read_text(encoding="utf-8")
    if "{{" in text:
        sys.exit("[A] 에 아직 치환되지 않은 자리표시자가 있습니다. publish 를 먼저 하세요.")
    if not meta.get("title"):
        sys.exit(f"{META} 의 title 이 비어 있습니다.")

    # 블로그가 여러 개일 수 있다. 좁은 지정이 넓은 지정을 이긴다.
    #   --blog-id  >  keywords.csv 의 naver_blog_id  >  .env 의 NAVER_BLOG_ID
    blog_id = (args.blog_id
               or meta.get("naver_blog_id")
               or load_env().get("NAVER_BLOG_ID", ""))
    blog_id = blog_id.strip()
    if not blog_id:
        sys.exit("네이버 블로그를 정해주세요. --blog-id, keywords.csv 의 "
                 "naver_blog_id, .env 의 NAVER_BLOG_ID 중 하나면 됩니다.")
    print(f"   네이버 블로그: {blog_id}")

    cmd = [sys.executable, "naver_draft.py",
           "--blog-id", blog_id,
           "--html", str(a),
           "--title", meta["title"],
           "--images", str(folder / IMAGES)]
    if (folder / TAGS).exists():
        cmd += ["--tags", str(folder / TAGS)]
    run(cmd)

    meta["naver_done"] = dt.datetime.now().isoformat(timespec="seconds")
    save_meta(folder, meta)


def cmd_done(args):
    folder = Path(args.folder)
    meta = load_meta(folder)
    rows = read_rows()
    row = find_row(rows, meta["keyword"])
    if row is None:
        sys.exit(f"keywords.csv 에서 찾지 못했습니다: {meta['keyword']}")

    if not meta.get("naver_done"):
        print("주의: 네이버 임시저장이 아직입니다. 그래도 기록합니다.")

    row["status"] = "done"
    row["google_url"] = meta.get("google_url", "")
    row["naver_done"] = "y" if meta.get("naver_done") else ""
    row["date"] = dt.date.today().isoformat()
    write_rows(rows)
    print(f"기록했습니다: {meta['keyword']} → {row['google_url']}")


def main():
    ap = argparse.ArgumentParser(description="글 한 편을 만드는 단계 실행기")
    ap.add_argument("--force", action="store_true", help="끝난 단계도 다시 한다")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("next", help="다음에 쓸 키워드를 고른다").set_defaults(fn=cmd_next)

    p = sub.add_parser("init", help="작업 폴더를 만든다")
    p.add_argument("keyword")
    p.set_defaults(fn=cmd_init)

    for name, fn, help_text in (
        ("status", cmd_status, "어디까지 됐는지 본다"),
        ("cards", cmd_cards, "카드 이미지를 만든다"),
        ("done", cmd_done, "keywords.csv 에 결과를 적는다"),
    ):
        p = sub.add_parser(name, help=help_text)
        p.add_argument("folder")
        p.set_defaults(fn=fn)

    p = sub.add_parser("publish", help="[B] 를 발행한다")
    p.add_argument("folder")
    p.add_argument("--labels", help="블로그스팟 라벨. 쉼표로 구분")
    p.set_defaults(fn=cmd_publish)

    p = sub.add_parser("naver", help="네이버에 임시저장한다")
    p.add_argument("folder")
    p.add_argument("--blog-id", help=".env 의 NAVER_BLOG_ID 대신 쓸 아이디")
    p.set_defaults(fn=cmd_naver)

    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
