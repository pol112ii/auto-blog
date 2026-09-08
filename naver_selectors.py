"""네이버 에디터 셀렉터 모음.

에디터가 개편되면 이 파일만 고치면 된다.
값은 후보 목록이며, 화면에 실제로 보이는 첫 번째 것을 쓴다.

네이버는 클래스명 뒤에 해시를 붙여(save_btn__bzc5B) 수시로 바꾼다.
그래서 후보를 짤 때 순서를 이렇게 둔다.
  1) 글자로 찾기      — 화면 문구는 잘 바뀌지 않는다
  2) 구조로 찾기      — se- 접두사는 에디터 세대가 바뀌지 않는 한 남는다
  3) 해시 붙은 클래스 — 가장 잘 깨진다. 맨 뒤에 둔다

확인 방법:  python naver_draft.py --blog-id <아이디> --inspect
"""

WRITE_URL = "https://blog.naver.com/{blog_id}/postwrite"

# 에디터 본체가 들어 있는 iframe
MAIN_FRAME = "#mainFrame"

SEL = {
    # 제목 입력 영역
    "title": [
        ".se-section-documentTitle [contenteditable='true']",
        ".se-documentTitle [contenteditable='true']",
        ".se-section-documentTitle .se-text-paragraph",
        ".se-placeholder:has-text('제목')",
    ],

    # 본문 입력 영역 (여기를 클릭해 커서를 둔 뒤 붙여넣는다)
    "body": [
        ".se-section-text [contenteditable='true']",
        ".se-component.se-text [contenteditable='true']",
        ".se-section-text .se-text-paragraph",
        ".se-content [contenteditable='true']",
    ],

    # 이미지 업로드용 숨은 file input (보이지 않아도 되므로 존재만 확인한다)
    "image_input": [
        "input.se-image-file-input",
        "input[type='file'][accept*='image']",
        "input[type='file']",
    ],

    # 태그 입력란
    "tag_input": [
        "input[placeholder*='태그']",
        ".tag_input",
        "#tag-input",
    ],

    # 임시저장 버튼 — 네이버 표기는 '저장'
    "save_draft": [
        "button:has-text('저장')",
        "a:has-text('저장')",
        ".save_btn",
    ],

    # ── 팝업류 ────────────────────────────────────────────────
    # "작성 중인 글이 있습니다" — 이어쓰기 대신 항상 새 글로 시작한다
    "popup_continue_cancel": [
        ".se-popup-button-cancel",
        "button:has-text('취소')",
    ],
    # 붙여넣기 시 뜨는 서식 유지 여부 — 서식을 유지해야 여백이 산다
    "popup_keep_format": [
        "button:has-text('유지')",
        ".se-popup-button-confirm",
    ],
    # 임시저장 완료 알림
    "popup_confirm": [
        ".se-popup-button-confirm",
        "button:has-text('확인')",
    ],
}

# 파일 input 은 숨어 있는 게 정상이라 '보임' 검사를 하지 않는다.
PRESENCE_ONLY = {"image_input"}

# 절대 누르면 안 되는 것. 실수로라도 클릭되지 않도록 여기 적어만 둔다.
NEVER_CLICK = [
    "button:has-text('발행')",
    ".publish_btn",
]
