#app/promote.py

'''
2026-07-24
등급 부여 스크립트 (최초 관리자 지정용)

등급은 관리자만 바꿀 수 있는데, 새 DB 에는 관리자가 없다.

    uv run python -m app.promote hong@example.com
    uv run python -m app.promote hong@example.com member
'''

import sys
from .database.connection import SessionFactory
from .database.orm import User, UserRole
from sqlalchemy import select


def promote(email: str, role: str) -> None:
    session = SessionFactory()
    try:
        user = session.scalar(select(User).where(User.email == email))
        if user is None:
            print(f"그런 계정이 없습니다: {email}")
            return

        user.role = role
        session.commit()
        print(f"{email} → {role}")
    finally:
        session.close()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("사용법: uv run python -m app.promote <email> [admin|member]")
        sys.exit(1)

    target_role = sys.argv[2] if len(sys.argv) > 2 else UserRole.ADMIN
    if target_role not in tuple(UserRole):
        print(f"등급은 {[r.value for r in UserRole]} 중 하나여야 합니다")
        sys.exit(1)

    promote(sys.argv[1], target_role)