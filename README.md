# auto-blog

키워드 하나로 구글 블로그에 완전판 글을 발행하고,
네이버 블로그에는 그 글로 유입시키는 요약글을 임시저장까지 해둔다.

사람이 하는 일은 셋뿐이다. **키워드 승인, 명령어 한 줄, 네이버 발행 버튼 클릭.**

## 처음 한 번만

```bash
pip install playwright
playwright install chromium

cp .env.example .env      # 값을 채운다
python blogger_auth.py    # 구글 refresh token 을 받는다
python doctor.py          # 빠진 게 없는지 본다
```

`.env` 는 git 에 올라가지 않는다. 비밀값은 여기에만 둔다.

## 쓰는 법

`keywords.csv` 에 한 줄 넣는다. `official_url` 은 반드시 사람이 채운다.

```csv
keyword,official_url,extra_urls,status,google_url,naver_done,date,naver_blog_id
청년도약계좌,https://www.kinfa.or.kr/,,,,,,
```

터미널에서:

```
/newpost                      맨 위 미처리 키워드
/newpost 청년도약계좌           키워드 지정
/newpost 청년도약계좌 다른아이디  네이버 블로그까지 지정
```

끝나면 구글 블로그에는 글이 올라가 있고,
네이버에는 소제목 이미지와 태그까지 채워진 글이 **임시저장** 되어 있다.
발행 버튼은 사람이 누른다.

## 키워드 찾기

```bash
python keyword_finder.py find 청년 지원금 대출
# candidates.csv 를 열어 쓸 줄의 use 에 y, official_url 을 채운 뒤
python keyword_finder.py adopt
```

`official_url` 이 비었거나 주소 형식이 아니면 옮기지 않는다.
이 칸은 절대 자동으로 채우지 않는다.

## 파일

| 파일 | 하는 일 |
|---|---|
| `prompts/post_generator.md` | 원고 작성 지시서. 원고는 Claude Code 가 직접 쓴다 |
| `pipeline.py` | 단계별 실행기. 실패한 단계만 다시 돌릴 수 있다 |
| `publish_blogger.py` | 블로그스팟 발행 + 발행 전 링크 검사 |
| `naver_draft.py` | 네이버 임시저장 (발행하지 않는다) |
| `naver_selectors.py` | 네이버 셀렉터 모음. 에디터가 바뀌면 여기만 고친다 |
| `naver_images.py` | 소제목 카드 이미지 생성 |
| `keyword_finder.py` | 키워드 후보 수집과 채택 |
| `doctor.py` | 준비 상태 점검 |

## 중간에 실패했다면

각 단계는 결과를 파일로 남기고 이미 끝난 일은 건너뛴다.
처음부터 다시 하지 말고 실패한 단계만 다시 돌린다.

```bash
python pipeline.py status posts/2026-09-08-청년도약계좌
python pipeline.py publish posts/2026-09-08-청년도약계좌
```

## 네이버 셀렉터가 안 맞을 때

네이버는 클래스 이름에 해시를 붙여 수시로 바꾼다.
어느 셀렉터가 살아 있는지 먼저 본다.

```bash
python naver_draft.py --blog-id <아이디> --inspect
```

`naver_selectors.py` 를 고친 뒤, 흐름이 여전히 온전한지 확인한다.
네이버에 접속하지 않고 가짜 에디터로 돌린다.

```bash
python tests/run_mock_test.py
```

## 원칙

- 유료 API 를 부르지 않는다. 원고는 Claude Code 가 쓴다.
- 없는 URL 을 지어내지 않는다. 링크가 하나라도 죽어 있으면 발행하지 않는다.
- 네이버는 임시저장까지만. 발행은 사람이 한다.
- 네이버 글과 구글 글은 역할이 다르다.
  네이버는 결론과 대표 수치를 담은 요약글, 구글은 표·절차·FAQ 까지 담은 완전판.
  문장이 겹치면 유사문서로 잡힌다.
- 비밀번호를 코드나 저장소에 두지 않는다. 네이버는 로그인된 크롬 프로필을 재사용한다.
