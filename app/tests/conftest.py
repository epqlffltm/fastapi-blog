#app/tests/conftest.py

'''
2026-07-21
테스트 공통 fixture

2026-07-23
인증 fixture 추가

2026-07-24
이메일/미인증 fixture 추가
분류 / 업로드 fixture 추가
권한 · 제재 fixture 추가

2026-07-28
OTP Lua 스크립트 동작을 반영한 Redis mock 추가
'''

from datetime import datetime, timedelta, timezone
from unittest.mock import DEFAULT, AsyncMock, Mock

import pytest
from fastapi.testclient import TestClient
from redis.asyncio import Redis

from app.api.dependency import get_current_user, get_current_user_optional
from app.database.cache import get_redis_client
from app.database.orm import User
from app.database.profile_repository import ProfileCommentRepository
from app.database.repository import (
    CategoryRepository,
    CommentRepository,
    LikeRepository,
    PostRepository,
    UploadRepository,
    UserRepository,
)
from app.main import app
from app.service.email import EmailService
from app.service.ratelimit import LoginRateLimitService
from app.service.upload import UploadService


@pytest.fixture
def client():
    return TestClient(app=app)


@pytest.fixture
def current_user():
    # 기본은 댓글만 가능한 회원. 더 필요한 테스트는 admin_client 를 쓴다
    return User(
        id=1,
        email="test@example.com",
        password="$2b$12$fakehashedpassword",
        token_version=0,
        nickname="tester",
        is_verified=True,
        can_comment=True,
        can_write_post=False,
        can_upload=False,
        can_manage_category=False,
        can_manage_user=False,
        can_manage_post=False,
        suspended_until=None,
        is_banned=False,
        created_at=datetime(2026, 7, 23, tzinfo=timezone.utc),
    )


@pytest.fixture
def auth_client(client, current_user):
    """로그인된 일반 회원 (댓글만)"""
    app.dependency_overrides[get_current_user] = lambda: current_user
    yield client
    app.dependency_overrides.clear()


@pytest.fixture
def admin_client(client, current_user):
    """모든 권한을 가진 회원"""
    current_user.grant_all()
    app.dependency_overrides[get_current_user] = lambda: current_user
    yield client
    app.dependency_overrides.clear()


@pytest.fixture
def unverified_client(client, current_user):
    """이메일 미인증 상태 (권한은 있지만 인증에서 먼저 걸린다)"""
    current_user.grant_all()
    current_user.is_verified = False
    app.dependency_overrides[get_current_user] = lambda: current_user
    yield client
    app.dependency_overrides.clear()


@pytest.fixture
def suspended_client(client, current_user):
    """기간 정지된 회원 (권한은 있지만 제재에서 걸린다)"""
    current_user.grant_all()
    current_user.suspended_until = datetime.now(timezone.utc) + timedelta(days=1)
    app.dependency_overrides[get_current_user] = lambda: current_user
    yield client
    app.dependency_overrides.clear()


@pytest.fixture
def banned_client(client, current_user):
    """강퇴된 회원"""
    current_user.grant_all()
    current_user.is_banned = True
    app.dependency_overrides[get_current_user] = lambda: current_user
    yield client
    app.dependency_overrides.clear()


@pytest.fixture
def mock_post_repo():
    repo = AsyncMock(spec=PostRepository)
    app.dependency_overrides[PostRepository] = lambda: repo
    yield repo
    app.dependency_overrides.clear()


@pytest.fixture
def mock_like_repo():
    repo = AsyncMock(spec=LikeRepository)
    app.dependency_overrides[LikeRepository] = lambda: repo
    yield repo
    app.dependency_overrides.clear()


@pytest.fixture
def mock_comment_repo():
    repo = AsyncMock(spec=CommentRepository)
    app.dependency_overrides[CommentRepository] = lambda: repo
    yield repo
    app.dependency_overrides.clear()


@pytest.fixture
def mock_profile_comment_repo():
    repo = AsyncMock(spec=ProfileCommentRepository)
    app.dependency_overrides[ProfileCommentRepository] = lambda: repo
    yield repo
    app.dependency_overrides.clear()


@pytest.fixture
def mock_user_repo():
    repo = AsyncMock(spec=UserRepository)
    app.dependency_overrides[UserRepository] = lambda: repo
    yield repo
    app.dependency_overrides.clear()


@pytest.fixture
def mock_category_repo():
    repo = AsyncMock(spec=CategoryRepository)
    app.dependency_overrides[CategoryRepository] = lambda: repo
    yield repo
    app.dependency_overrides.clear()


@pytest.fixture
def mock_upload_repo():
    repo = AsyncMock(spec=UploadRepository)
    app.dependency_overrides[UploadRepository] = lambda: repo
    yield repo
    app.dependency_overrides.clear()


@pytest.fixture
def mock_upload_service():
    # save 가 async 이므로 AsyncMock
    service = AsyncMock(spec=UploadService)
    app.dependency_overrides[UploadService] = lambda: service
    yield service
    app.dependency_overrides.clear()


@pytest.fixture
def mock_redis():
    redis = Mock(spec=Redis)
    # redis.asyncio 명령은 await 대상이므로 각 메서드를 AsyncMock으로 둔다.
    redis.set = AsyncMock()
    redis.get = AsyncMock()
    redis.delete = AsyncMock()
    redis.aclose = AsyncMock()

    eval_mock = AsyncMock()

    async def eval_side_effect(script, _num_keys, *args):
        # 개별 테스트가 return_value를 지정하면 그 값을 최우선으로 쓴다.
        forced_result = eval_mock._mock_return_value
        if forced_result is not DEFAULT:
            return forced_result

        if "OTP_SAVE_AND_RESET_ATTEMPTS" in script:
            # Lua 내부 DEL을 테스트 상태에도 반영한다.
            await redis.delete(args[1])
            return 1

        if "OTP_VERIFY_AND_CONSUME" in script:
            saved = redis.get.return_value
            if saved is None:
                return -1

            provided = str(args[2])
            if str(saved) == provided:
                # 실제 Redis에서는 두 DEL이 EVAL 내부에서 한 번에 수행된다.
                await redis.delete(args[0], args[1])
                return 1
            return 0

        # OTP 발급 슬롯 등 성공이 기본인 스크립트.
        return 1

    eval_mock.side_effect = eval_side_effect
    redis.eval = eval_mock

    app.dependency_overrides[get_redis_client] = lambda: redis
    yield redis
    app.dependency_overrides.clear()


@pytest.fixture
def mock_rate_limit():
    """로그인 레이트리밋 — 기본은 통과. 막히는 경우는 테스트가 직접 켠다"""
    service = AsyncMock(spec=LoginRateLimitService)
    service.is_blocked.return_value = False
    app.dependency_overrides[LoginRateLimitService] = lambda: service
    yield service
    app.dependency_overrides.clear()


@pytest.fixture
def mock_email_service():
    service = Mock(spec=EmailService)
    app.dependency_overrides[EmailService] = lambda: service
    yield service
    app.dependency_overrides.clear()


@pytest.fixture
def admin_viewer(client, current_user):
    """공개 조회(get_current_user_optional)를 관리자 눈으로 본다"""
    current_user.grant_all()      # can_manage_post 포함
    app.dependency_overrides[get_current_user_optional] = lambda: current_user
    yield client
    app.dependency_overrides.pop(get_current_user_optional, None)
