#app/promote.py

'''
2026-07-24
권한 부여 스크립트 (최초 관리자 지정용)

권한은 can_manage_user 를 가진 사람만 바꿀 수 있는데,
새 DB 에는 그런 사람이 없다. 그 닭과 달걀을 끊는 유일한 통로다.
서버 밖에서만 실행된다.

    uv run python -m app.promote hong@example.com           # 모든 권한
    uv run python -m app.promote hong@example.com revoke    # 댓글만 남김
'''

import sys
from sqlalchemy import select
from .database.connection import SessionFactory
from .database.orm import User, PERMISSIONS


def promote(email: str, revoke: bool) -> None:
    session = SessionFactory()
    try:
        user = session.scalar(select(User).where(User.email == email))
        if user is None:
            print(f"그런 계정이 없습니다: {email}")
            return

        if revoke:
            user.revoke_all()
            user.can_comment = True
        else:
            user.grant_all()
            user.is_verified = True     # 권한만 주고 인증이 막혀 있으면 쓸모가 없다
            user.is_banned = False
            user.suspended_until = None

        session.commit()
        granted = [label for name, label in PERMISSIONS if getattr(user, name)]
        print(f"{email} → {', '.join(granted) or '권한 없음'}")
    finally:
        session.close()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("사용법: uv run python -m app.promote <email> [revoke]")
        sys.exit(1)

    promote(sys.argv[1], revoke=(len(sys.argv) > 2 and sys.argv[2] == "revoke"))