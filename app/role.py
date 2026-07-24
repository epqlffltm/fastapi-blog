#app/role.py

'''
2026-07-24
회원 등급
'''

from enum import IntEnum


class Role(IntEnum):
    """숫자가 클수록 권한이 넓다.

    중간 등급(예: 글만 쓰는 필자)이 필요해지면 사이에 값을 넣으면 되고,
    검사는 전부 부등호라 기존 코드를 고칠 필요가 없다.
    """

    MEMBER = 1    # 댓글만 쓸 수 있다
    ADMIN = 2     # 글쓰기 + 분류 관리 + 등급 변경