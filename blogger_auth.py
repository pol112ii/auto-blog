#!/usr/bin/env python3
"""Blogger refresh token 을 한 번만 받아내는 도우미.

  python blogger_auth.py

브라우저로 구글 로그인 → 승인하면 refresh token 을 출력한다.
출력된 값을 .env 의 BLOGGER_REFRESH_TOKEN 에 붙여넣으면 끝이고,
이 스크립트는 다시 실행할 일이 없다.
"""

import json
import secrets
import sys
import urllib.parse
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer

from publish_blogger import TOKEN_URL, load_env

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
SCOPE = "https://www.googleapis.com/auth/blogger"
PORT = 8765
REDIRECT_URI = f"http://localhost:{PORT}/"

_result = {}


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        query = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        _result.update({k: v[0] for k, v in query.items()})
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        done = "code" in _result
        msg = "인증 완료. 터미널로 돌아가세요." if done else "인증 실패. 터미널을 확인하세요."
        self.wfile.write(f"<meta charset=utf-8><h2>{msg}</h2>".encode())

    def log_message(self, *args):  # 서버 접속 로그는 띄우지 않는다
        pass


def main():
    env = load_env()
    client_id = env.get("BLOGGER_CLIENT_ID")
    client_secret = env.get("BLOGGER_CLIENT_SECRET")
    if not client_id or not client_secret:
        sys.exit(".env 에 BLOGGER_CLIENT_ID 와 BLOGGER_CLIENT_SECRET 를 먼저 넣어주세요.")

    state = secrets.token_urlsafe(16)
    params = {
        "client_id": client_id,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": SCOPE,
        "access_type": "offline",
        "prompt": "consent",          # refresh token 을 반드시 받기 위해
        "state": state,
    }
    url = f"{AUTH_URL}?{urllib.parse.urlencode(params)}"

    print("아래 주소를 브라우저에서 열어 구글 계정으로 승인하세요.\n")
    print(url + "\n")
    try:
        webbrowser.open(url)
    except Exception:
        pass

    print(f"승인을 기다리는 중... (localhost:{PORT})")
    server = HTTPServer(("127.0.0.1", PORT), Handler)
    server.handle_request()

    if _result.get("state") != state:
        sys.exit("state 값이 맞지 않습니다. 처음부터 다시 실행해주세요.")
    if "code" not in _result:
        sys.exit(f"인증이 거부되었습니다: {_result.get('error', '알 수 없음')}")

    data = urllib.parse.urlencode({
        "code": _result["code"],
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": REDIRECT_URI,
        "grant_type": "authorization_code",
    }).encode()
    with urllib.request.urlopen(urllib.request.Request(TOKEN_URL, data=data)) as r:
        tokens = json.load(r)

    refresh = tokens.get("refresh_token")
    if not refresh:
        sys.exit("refresh_token 이 오지 않았습니다. 구글 계정의 기존 앱 권한을 해제하고 다시 시도하세요.")

    print("\n성공했습니다. 아래 한 줄을 .env 에 넣으세요.\n")
    print(f"BLOGGER_REFRESH_TOKEN={refresh}\n")


if __name__ == "__main__":
    main()
