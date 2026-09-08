#!/usr/bin/env python3
"""[B] 블로그스팟 HTML 을 Blogger 에 발행하고 글 URL 을 출력한다.

  python publish_blogger.py posts/2026-09-08-청년도약계좌/B.html
  python publish_blogger.py B.html --draft --title "제목" --labels 지원금,금융

발행 전에 본문의 모든 링크를 검사한다.
[URL_확인필요] 가 남아 있거나 죽은 링크가 하나라도 있으면
발행하지 않고 어떤 링크가 문제인지 알려준다.
"""

import argparse
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

TOKEN_URL = "https://oauth2.googleapis.com/token"
API_BASE = "https://www.googleapis.com/blogger/v3/blogs"
ENV_PATH = Path(__file__).parent / ".env"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 " \
     "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
PLACEHOLDER = "[URL_확인필요]"
LINK_TIMEOUT = 15


# ── .env ───────────────────────────────────────────────────────────
def load_env(path=ENV_PATH):
    env = {}
    if not Path(path).exists():
        return env
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        env[key.strip()] = value.strip().strip('"').strip("'")
    return env


# ── HTML 파싱 ──────────────────────────────────────────────────────
class LinkCollector(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
        self.title = None
        self._grab = None
        self._buf = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "a" and attrs.get("href"):
            self.links.append(attrs["href"].strip())
        if tag in ("h1", "h2") and self.title is None and self._grab is None:
            self._grab = tag
            self._buf = []

    def handle_data(self, data):
        if self._grab:
            self._buf.append(data)

    def handle_endtag(self, tag):
        if tag == self._grab:
            text = "".join(self._buf).strip()
            if text:
                self.title = text
            self._grab = None


def parse_html(html):
    parser = LinkCollector()
    parser.feed(html)
    return parser.links, parser.title


# ── 링크 검사 ──────────────────────────────────────────────────────
def probe(url):
    """살아 있으면 None, 문제가 있으면 사유 문자열을 돌려준다."""
    for method in ("HEAD", "GET"):
        req = urllib.request.Request(url, method=method, headers={"User-Agent": UA})
        try:
            with urllib.request.urlopen(req, timeout=LINK_TIMEOUT) as r:
                if r.status < 400:
                    return None
                return f"HTTP {r.status}"
        except urllib.error.HTTPError as e:
            # HEAD 를 막아둔 서버가 흔하다. GET 으로 한 번 더 본다.
            if method == "HEAD" and e.code in (403, 405, 501):
                continue
            return f"HTTP {e.code}"
        except urllib.error.URLError as e:
            return f"연결 실패: {e.reason}"
        except Exception as e:
            return f"오류: {e}"
    return None


def check_links(html):
    """발행을 막아야 할 사유 목록을 돌려준다."""
    problems = []

    if PLACEHOLDER in html:
        problems.append(f"{PLACEHOLDER} 가 본문에 남아 있습니다. 실제 URL 로 바꿔주세요.")

    leftovers = sorted(set(re.findall(r"\{\{[A-Z_]+\}\}", html)))
    if leftovers:
        problems.append(f"치환되지 않은 자리표시자: {', '.join(leftovers)}")

    links, _ = parse_html(html)
    seen = set()
    for href in links:
        if href in seen:
            continue
        seen.add(href)

        if PLACEHOLDER in href:
            problems.append(f"{href} → 확인이 필요한 링크입니다")
            continue
        if href.startswith(("#", "mailto:", "tel:", "javascript:")):
            continue
        if not href.startswith(("http://", "https://")):
            problems.append(f"{href} → 절대 주소가 아닙니다")
            continue

        reason = probe(href)
        print(f"  {'OK ' if reason is None else 'NG '} {href}"
              + (f"  ({reason})" if reason else ""), file=sys.stderr)
        if reason:
            problems.append(f"{href} → {reason}")

    return problems


# ── Blogger API ────────────────────────────────────────────────────
def get_access_token(env):
    missing = [k for k in ("BLOGGER_CLIENT_ID", "BLOGGER_CLIENT_SECRET",
                           "BLOGGER_REFRESH_TOKEN") if not env.get(k)]
    if missing:
        sys.exit(f".env 에 다음 값이 없습니다: {', '.join(missing)}\n"
                 f"README 의 OAuth 절차를 먼저 진행해주세요.")

    data = urllib.parse.urlencode({
        "client_id": env["BLOGGER_CLIENT_ID"],
        "client_secret": env["BLOGGER_CLIENT_SECRET"],
        "refresh_token": env["BLOGGER_REFRESH_TOKEN"],
        "grant_type": "refresh_token",
    }).encode()
    try:
        with urllib.request.urlopen(urllib.request.Request(TOKEN_URL, data=data)) as r:
            return json.load(r)["access_token"]
    except urllib.error.HTTPError as e:
        sys.exit(f"액세스 토큰 발급 실패 (HTTP {e.code}): {e.read().decode(errors='replace')}")


def resolve_blog_id(token, blog_url):
    """블로그 주소로 blogId 를 찾는다. 관리자 페이지에서 숫자를 뒤질 필요가 없다."""
    url = f"{API_BASE}/byurl?url={urllib.parse.quote(blog_url, safe='')}"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    try:
        with urllib.request.urlopen(req) as r:
            return json.load(r)["id"]
    except urllib.error.HTTPError as e:
        sys.exit(f"블로그를 찾지 못했습니다 ({blog_url}, HTTP {e.code}): "
                 f"{e.read().decode(errors='replace')}")


def insert_post(token, blog_id, title, content, labels, is_draft):
    url = f"{API_BASE}/{blog_id}/posts/"
    if is_draft:
        url += "?isDraft=true"
    body = {"kind": "blogger#post", "title": title, "content": content}
    if labels:
        body["labels"] = labels

    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={"Authorization": f"Bearer {token}",
                 "Content-Type": "application/json; charset=UTF-8"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        sys.exit(f"발행 실패 (HTTP {e.code}): {e.read().decode(errors='replace')}")


# ── main ───────────────────────────────────────────────────────────
def main():
    ap = argparse.ArgumentParser(description="블로그스팟 HTML 발행")
    ap.add_argument("html", help="발행할 HTML 파일 ([B] 원고)")
    ap.add_argument("--title", help="글 제목. 없으면 본문의 첫 <h1>/<h2> 를 쓴다")
    ap.add_argument("--labels", help="라벨. 쉼표로 구분")
    ap.add_argument("--draft", action="store_true", help="임시저장 상태로 올린다")
    ap.add_argument("--blog-id", help=".env 의 BLOGGER_BLOG_ID 대신 쓸 블로그 ID")
    ap.add_argument("--blog-url", help="블로그 주소. ID 대신 이것만 줘도 된다")
    ap.add_argument("--skip-link-check", action="store_true",
                    help="링크 검사를 건너뛴다 (권장하지 않음)")
    args = ap.parse_args()

    env = load_env()
    blog_id = args.blog_id or env.get("BLOGGER_BLOG_ID")
    blog_url = args.blog_url or env.get("BLOGGER_BLOG_URL")
    if not blog_id and not blog_url:
        sys.exit("블로그를 지정해주세요. .env 의 BLOGGER_BLOG_ID 또는 BLOGGER_BLOG_URL,\n"
                 "아니면 --blog-id / --blog-url 을 주세요.")

    path = Path(args.html)
    if not path.exists():
        sys.exit(f"파일이 없습니다: {path}")
    html = path.read_text(encoding="utf-8")

    _, found_title = parse_html(html)
    title = args.title or found_title
    if not title:
        sys.exit("제목을 찾지 못했습니다. --title 로 직접 지정해주세요.")

    if args.skip_link_check:
        print("링크 검사를 건너뜁니다.", file=sys.stderr)
    else:
        print("링크를 검사합니다...", file=sys.stderr)
        problems = check_links(html)
        if problems:
            print("\n발행을 중단했습니다. 아래 문제를 먼저 고쳐주세요.\n", file=sys.stderr)
            for p in problems:
                print(f"  - {p}", file=sys.stderr)
            sys.exit(1)
        print("링크 이상 없음.\n", file=sys.stderr)

    labels = [s.strip() for s in args.labels.split(",")] if args.labels else None
    token = get_access_token(env)
    if not blog_id:
        blog_id = resolve_blog_id(token, blog_url)
        print(f"블로그 ID: {blog_id}  ({blog_url})", file=sys.stderr)
    post = insert_post(token, blog_id, title, html, labels, args.draft)

    state = "임시저장" if args.draft else "발행"
    print(f"{state} 완료: {post.get('title')}", file=sys.stderr)
    print(post.get("url", ""))   # 다음 단계가 받아쓸 수 있게 stdout 은 URL 만


if __name__ == "__main__":
    main()
