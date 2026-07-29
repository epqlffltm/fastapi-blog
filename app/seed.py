#app/seed.py

'''
2026-07-20
초기 데이터를 DB에 넣는 시드 스크립트 (최초 1회)

2026-07-29
비밀번호가 공개된 테스트 계정 9개와 데모 글·댓글을 제거.
분류와 관리자 계정 하나만 만든다.

계정 정보는 코드에 박지 않고 .env 에서 읽는다. 이전 판본은
"seedpass123" 으로 전권 계정 셋을 만들었는데, 배포한 서버에서
돌리면 그대로 백도어가 된다.

또 async 전환(62f1788) 때 이 파일이 같이 옮겨지지 않아
flush/commit 이 await 되지 않은 채 버려지고 있었다.
"시드 완료" 를 출력하면서 실제로는 아무것도 저장하지 않았다.

사용법:
    uv run python -m app.seed
    docker compose run --rm app python -m app.seed
'''

import asyncio
import sys

from sqlalchemy import select

from .database.connection import SessionFactory, settings
from .database.orm import Category, User
from .service.auth import AuthService
from .service.password import (
    BCRYPT_MAX_PASSWORD_BYTES,
    is_bcrypt_password_length_valid,
)

MIN_PASSWORD_LENGTH = 8      # 가입 정책(NewPassword)과 같은 값

# 분류 (slug: URL용 / name: 화면 표시용)
CATEGORIES = [
    {"slug": "dnd", "name": "TRPG", "display_order": 0},
    {"slug": "dev", "name": "개발", "display_order": 1},
    {"slug": "daily", "name": "일상", "display_order": 2},
    # 미분류: 분류를 삭제하면 그 글들이 여기로 모인다.
    # 항상 존재해야 하고 삭제할 수 없다. display_order 를 크게 줘 맨 아래로
    {"slug": "uncategorized", "name": "미분류", "display_order": 99},
]


def read_admin_credentials() -> tuple[str, str, str]:
    """.env 에서 관리자 계정 정보를 읽고 검증한다.

    이메일은 SEED_ADMIN_EMAIL 을 우선 보고, 없으면 SMTP_USER 로 넘어간다.
    메일 발송 계정과 관리자 계정은 원래 별개이므로, 하나로 쓰더라도
    나중에 갈라놓을 수 있게 두 단계로 둔다.

    앱과 같은 Settings 를 쓴다. 로컬에서는 .env 를, 컨테이너에서는
    compose 가 주입한 환경변수를 읽으므로 양쪽이 같은 경로로 동작한다.
    """
    email = (settings.seed_admin_email or settings.smtp_user or "").strip()
    password = settings.seed_admin_password
    nickname = settings.seed_admin_nickname.strip()

    if not email:
        raise SystemExit(
            ".env 에 SEED_ADMIN_EMAIL 또는 SMTP_USER 가 필요합니다."
        )
    if not password:
        raise SystemExit(
            ".env 에 SEED_ADMIN_PASSWORD 가 필요합니다.\n"
            "  예) SEED_ADMIN_PASSWORD=고를-비밀번호"
        )
    if len(password) < MIN_PASSWORD_LENGTH:
        raise SystemExit(
            f"SEED_ADMIN_PASSWORD 는 {MIN_PASSWORD_LENGTH}자 이상이어야 합니다."
        )
    # 문자 수가 아니라 바이트 수다. 한글은 한 글자가 3바이트라
    # 25자만 넘어도 bcrypt 한도를 넘긴다
    if not is_bcrypt_password_length_valid(password):
        raise SystemExit(
            f"SEED_ADMIN_PASSWORD 가 UTF-8 {BCRYPT_MAX_PASSWORD_BYTES}바이트를 넘습니다."
        )

    # 닉네임을 안 주면 이메일 앞부분을 쓴다
    return email, password, nickname or email.split("@")[0]


async def ensure_categories(session) -> list[str]:
    """없는 분류만 추가한다. 다시 돌려도 중복이 생기지 않는다."""
    existing = set(
        (await session.scalars(select(Category.slug))).all()
    )
    added = []
    for data in CATEGORIES:
        if data["slug"] in existing:
            continue
        session.add(Category(**data))
        added.append(data["slug"])
    return added


async def ensure_admin(session, email: str, password: str, nickname: str) -> bool:
    """관리자 계정을 만든다. 이미 있으면 건드리지 않는다.

    이미 있는 계정의 비밀번호를 덮어쓰지 않는 게 중요하다.
    시드를 다시 돌렸다고 운영 중 계정의 비밀번호가 .env 값으로
    되돌아가면 그게 사고다.
    """
    exists = await session.scalar(
        select(User).where(User.email == email)
    )
    if exists is not None:
        return False

    user = User.create(
        email=email,
        hashed_password=AuthService().hash_password(password),
        nickname=nickname,
    )
    user.is_verified = True      # 시드 계정은 이메일 인증을 건너뛴다
    user.grant_all()
    session.add(user)
    return True


async def seed() -> None:
    email, password, nickname = read_admin_credentials()

    async with SessionFactory() as session:
        added_categories = await ensure_categories(session)
        created_admin = await ensure_admin(session, email, password, nickname)
        await session.commit()

    # 비밀번호는 절대 출력하지 않는다
    if added_categories:
        print(f"분류 추가: {', '.join(added_categories)}")
    else:
        print("분류: 이미 모두 존재")

    if created_admin:
        print(f"관리자 생성: {email} (닉네임 {nickname}, 전권)")
    else:
        print(f"관리자: {email} 계정이 이미 있어 건너뜀")


if __name__ == "__main__":
    try:
        asyncio.run(seed())
    except SystemExit as error:
        print(error, file=sys.stderr)
        raise