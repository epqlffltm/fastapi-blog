#app/service/markdown.py

'''
2026-07-24
마크다운 본문에서 값 뽑아내기
'''

import re

# ![alt](url) 의 url 부분. 제목이 붙은 ![](url "제목") 형태도 url 까지만 잡는다
_IMAGE_PATTERN = re.compile(r"!\[[^\]]*\]\(\s*([^)\s]+)")


def extract_first_image(contents: str) -> str | None:
    """본문 첫 이미지 주소. 목록의 미리보기로 쓴다"""
    match = _IMAGE_PATTERN.search(contents)
    return match.group(1) if match else None