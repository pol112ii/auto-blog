"""네이버 에디터 셀렉터 모음.

에디터가 개편되면 이 파일만 고치면 된다.
값은 후보 목록이며, 화면에 실제로 보이는 첫 번째 것을 쓴다.
확인 방법:  python naver_draft.py --inspect
"""

WRITE_URL = "https://blog.naver.com/{blog_id}/postwrite"

# 에디터 본체가 들어 있는 iframe
MAIN_FRAME = "#mainFrame"

SEL = {
    # 제목 입력 영역
    "title": [
        ".se-section-documentTitle .se-text-paragraph",
        ".se-documentTitle .se-text-paragraph",
        ".se-placeholder.__se_placeholder",
    ],

    # 본문 입력 영역 (여기를 클릭해 커서를 둔 뒤 붙여넣는다)
    "body": [
        ".se-section-text .se-text-paragraph",
        ".se-component.se-text .se-text-paragraph",
        ".se-content",
    ],

    # 이미지 업로드용 숨은 file input
    "image_input": [
        "input.se-image-file-input",
        "input[type=file][accept*=image]",
        "#hidden-file-input",
    ],

    # 태그 입력란
    "tag_input": [
        ".tag_input__rvUB5",
        "#tag-input",
        "input[placeholder*='태그']",
    ],

    # 임시저장 버튼
    "save_draft": [
        ".save_btn__bzc5B",
        "button.se-save-button",
        "button:has-text('저장')",
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

# 절대 누르면 안 되는 것. 실수로라도 클릭되지 않도록 여기 적어만 둔다.
NEVER_CLICK = [
    ".publish_btn__m9KHH",
    "button:has-text('발행')",
]
