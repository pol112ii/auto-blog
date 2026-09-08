#!/usr/bin/env python3
"""키워드 후보를 모아 점수를 매긴다.

  python keyword_finder.py find 청년 지원금 대출
  python keyword_finder.py adopt

find   시드 키워드의 연관 키워드와 검색량을 모아 candidates.csv 로 낸다.
adopt  candidates.csv 에서 use 칸에 y 를 적은 줄만 keywords.csv 로 옮긴다.

official_url 은 사람이 직접 채운다. 절대 추측해서 넣지 않는다.
"""

import argparse
import base64
import csv
import hashlib
import hmac
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from publish_blogger import load_env

ROOT = Path(__file__).resolve().parent
KEYWORDS = ROOT / "keywords.csv"
CANDIDATES = ROOT / "candidates.csv"

AD_HOST = "https://api.searchad.naver.com"
AD_PATH = "/keywordstool"
AC_URL = "https://ac.search.naver.com/nx/ac"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 " \
     "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"

FIELDS = ["keyword", "volume", "competition", "score", "use", "official_url"]

# 경쟁이 심할수록 같은 검색량이라도 가치가 떨어진다.
COMPETITION_WEIGHT = {"낮음": 1.0, "중간": 0.55, "높음": 0.3, "": 0.55}

TOP_N = 40


# ── 네이버 검색광고 API ────────────────────────────────────────────
def ad_headers(env, method, path):
    ts = str(round(time.time() * 1000))
    message = f"{ts}.{method}.{path}"
    signature = base64.b64encode(hmac.new(
        env["NAVER_AD_SECRET_KEY"].encode(), message.encode(), hashlib.sha256
    ).digest()).decode()
    return {
        "X-Timestamp": ts,
        "X-API-KEY": env["NAVER_AD_API_KEY"],
        "X-Customer": str(env["NAVER_AD_CUSTOMER_ID"]),
        "X-Signature": signature,
    }


def fetch_related(env, seeds):
    """키워드도구에서 연관 키워드와 월간 검색량을 받는다."""
    rows = []
    # 키워드도구는 한 번에 5개까지 받는다.
    for i in range(0, len(seeds), 5):
        chunk = [s.replace(" ", "") for s in seeds[i:i + 5]]
        query = urllib.parse.urlencode({
            "hintKeywords": ",".join(chunk), "showDetail": "1"})
        path = f"{AD_PATH}?{query}"
        req = urllib.request.Request(AD_HOST + path,
                                     headers=ad_headers(env, "GET", AD_PATH))
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                rows += json.load(r).get("keywordList", [])
        except urllib.error.HTTPError as e:
            sys.exit(f"검색광고 API 오류 (HTTP {e.code}): "
                     f"{e.read().decode(errors='replace')}")
        time.sleep(0.4)      # 연속 호출 간격
    return rows


def as_count(value):
    """'< 10' 같은 값이 섞여 온다."""
    if isinstance(value, int):
        return value
    text = str(value).replace("<", "").replace(",", "").strip()
    try:
        return int(text)
    except ValueError:
        return 0


def parse_ad_rows(rows):
    out = {}
    for row in rows:
        keyword = row.get("relKeyword", "").strip()
        if not keyword:
            continue
        volume = as_count(row.get("monthlyPcQcCnt")) \
            + as_count(row.get("monthlyMobileQcCnt"))
        out[keyword] = {
            "keyword": keyword,
            "volume": volume,
            "competition": row.get("compIdx", "") or "",
        }
    return out


# ── 자동완성 ───────────────────────────────────────────────────────
def fetch_autocomplete(word):
    """자동완성으로 후보를 넓힌다. 키가 없어도 쓸 수 있다."""
    query = urllib.parse.urlencode({
        "q": word, "st": "100", "r_format": "json", "frm": "nv", "ans": "2"})
    req = urllib.request.Request(f"{AC_URL}?{query}", headers={"User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.load(r)
    except Exception:
        return []

    found = []
    for group in data.get("items", []):
        for item in group:
            if isinstance(item, list) and item and isinstance(item[0], str):
                found.append(item[0].strip())
    return found


# ── 점수 ───────────────────────────────────────────────────────────
def score_of(volume, competition):
    """검색량이 클수록, 경쟁이 약할수록 높다.

    검색량은 그대로 쓰면 대형 키워드가 표를 다 덮어버려서
    제곱근으로 눌러 롱테일이 살아남게 한다.
    """
    weight = COMPETITION_WEIGHT.get(competition, COMPETITION_WEIGHT[""])
    return round((volume ** 0.5) * weight, 1)


# ── csv ────────────────────────────────────────────────────────────
def read_csv(path):
    if not Path(path).exists():
        return []
    with Path(path).open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def existing_keywords():
    return {r.get("keyword", "").strip()
            for r in read_csv(KEYWORDS) if r.get("keyword", "").strip()}


def write_candidates(rows):
    with CANDIDATES.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)


# ── find ───────────────────────────────────────────────────────────
def cmd_find(args):
    env = load_env()
    have_api = all(env.get(k) for k in
                   ("NAVER_AD_API_KEY", "NAVER_AD_SECRET_KEY", "NAVER_AD_CUSTOMER_ID"))

    seeds = list(args.seeds)
    if args.autocomplete:
        print("자동완성으로 후보를 넓힙니다...")
        for seed in args.seeds:
            found = fetch_autocomplete(seed)
            print(f"   {seed} → {len(found)}개")
            seeds += found
            time.sleep(0.3)
    seeds = list(dict.fromkeys(seeds))       # 순서 유지하며 중복 제거

    if have_api:
        print(f"\n검색광고 API 로 {len(seeds)}개 시드의 연관 키워드를 받습니다...")
        data = parse_ad_rows(fetch_related(env, seeds))
    else:
        print("\n검색광고 API 키가 없습니다. 검색량 없이 후보만 냅니다.")
        print("(.env 의 NAVER_AD_API_KEY / NAVER_AD_SECRET_KEY / "
              "NAVER_AD_CUSTOMER_ID)")
        data = {s: {"keyword": s, "volume": 0, "competition": ""} for s in seeds}

    already = existing_keywords()
    rows = []
    dropped_known = dropped_small = 0
    for item in data.values():
        if item["keyword"] in already:
            dropped_known += 1
            continue
        if item["volume"] < args.min_volume:
            dropped_small += 1
            continue
        rows.append({
            "keyword": item["keyword"],
            "volume": item["volume"],
            "competition": item["competition"],
            "score": score_of(item["volume"], item["competition"]),
            "use": "",
            "official_url": "",     # 사람이 채운다. 지어내지 않는다.
        })

    rows.sort(key=lambda r: r["score"], reverse=True)
    rows = rows[:args.top]
    write_candidates(rows)

    print(f"\n후보 {len(data)}개 중 이미 쓴 키워드 {dropped_known}개, "
          f"검색량 미달 {dropped_small}개를 뺐습니다.")
    print(f"{len(rows)}개를 {CANDIDATES.name} 에 적었습니다.\n")
    for row in rows[:10]:
        print(f"   {row['score']:>7}  {row['volume']:>8}회  "
              f"{row['competition'] or '-':4}  {row['keyword']}")
    if len(rows) > 10:
        print(f"   ... 나머지 {len(rows) - 10}개는 파일에서 보세요.")
    print(f"\n쓸 키워드의 use 칸에 y 를 적고 official_url 을 채운 뒤 "
          f"'python keyword_finder.py adopt' 를 실행하세요.")


# ── adopt ──────────────────────────────────────────────────────────
def cmd_adopt(args):
    rows = read_csv(CANDIDATES)
    if not rows:
        sys.exit(f"{CANDIDATES.name} 이 없습니다. find 를 먼저 하세요.")

    picked = [r for r in rows if r.get("use", "").strip().lower() == "y"]
    if not picked:
        sys.exit("use 칸에 y 를 적은 줄이 없습니다.")

    already = existing_keywords()
    moved, skipped = [], []
    for row in picked:
        keyword = row.get("keyword", "").strip()
        url = row.get("official_url", "").strip()
        if keyword in already:
            skipped.append((keyword, "이미 keywords.csv 에 있음"))
        elif not url:
            skipped.append((keyword, "official_url 이 비어 있음"))
        elif not url.startswith(("http://", "https://")):
            skipped.append((keyword, f"주소 형식이 아님: {url}"))
        else:
            moved.append(row)

    if moved:
        header = read_csv(KEYWORDS)
        fieldnames = list(header[0].keys()) if header else [
            "keyword", "official_url", "extra_urls", "status",
            "google_url", "naver_done", "date", "naver_blog_id"]
        if not KEYWORDS.exists():
            fieldnames = fieldnames
        with KEYWORDS.open("a", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fieldnames)
            if not KEYWORDS.exists() or KEYWORDS.stat().st_size == 0:
                w.writeheader()
            for row in moved:
                w.writerow({"keyword": row["keyword"],
                            "official_url": row["official_url"].strip()})

        # 옮긴 줄은 후보 목록에서 뺀다
        names = {r["keyword"] for r in moved}
        write_candidates([r for r in rows if r["keyword"] not in names])

    print(f"{len(moved)}개를 keywords.csv 로 옮겼습니다.")
    for row in moved:
        print(f"   {row['keyword']}  →  {row['official_url']}")
    for keyword, reason in skipped:
        print(f"   건너뜀: {keyword} ({reason})")


def main():
    ap = argparse.ArgumentParser(description="키워드 후보 수집")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("find", help="후보를 모아 candidates.csv 로 낸다")
    p.add_argument("seeds", nargs="+", help="시드 키워드")
    p.add_argument("--top", type=int, default=TOP_N, help=f"상위 몇 개 (기본 {TOP_N})")
    p.add_argument("--min-volume", type=int, default=100,
                   help="이 검색량 미만은 버린다 (기본 100)")
    p.add_argument("--no-autocomplete", dest="autocomplete", action="store_false",
                   help="자동완성으로 넓히지 않는다")
    p.set_defaults(fn=cmd_find)

    p = sub.add_parser("adopt", help="use=y 인 줄을 keywords.csv 로 옮긴다")
    p.set_defaults(fn=cmd_adopt)

    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
