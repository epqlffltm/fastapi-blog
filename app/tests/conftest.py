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
'''

import pytest
from datetime import datetime, timedelta, timezone
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, Mock
from redis import Redis
from app.main import app
from app.database.orm import User
from app.database.repository import PostRepository, CommentRepository, UserRepository,CategoryRepository, UploadRepository
from app.database.cache import get_redis_client
from app.api.dependency import get_current_user
from app.service.email import EmailService
from app.service.upload import UploadService
from app.api.dependency import get_current_user, get_current_user_optional


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
    repo = Mock(spec=PostRepository)
    app.dependency_overrides[PostRepository] = lambda: repo
    yield repo
    app.dependency_overrides.clear()


@pytest.fixture
def mock_comment_repo():
    repo = Mock(spec=CommentRepository)
    app.dependency_overrides[CommentRepository] = lambda: repo
    yield repo
    app.dependency_overrides.clear()


@pytest.fixture
def mock_user_repo():
    repo = Mock(spec=UserRepository)
    app.dependency_overrides[UserRepository] = lambda: repo
    yield repo
    app.dependency_overrides.clear()


@pytest.fixture
def mock_category_repo():
    repo = Mock(spec=CategoryRepository)
    app.dependency_overrides[CategoryRepository] = lambda: repo
    yield repo
    app.dependency_overrides.clear()


@pytest.fixture
def mock_upload_repo():
    repo = Mock(spec=UploadRepository)
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
    app.dependency_overrides[get_redis_client] = lambda: redis
    yield redis
    app.dependency_overrides.clear()


@pytest.fixture
def mock_email_service():
    service = Mock(spec=EmailService)
    app.dependency_overrides[EmailService] = lambda: service
    yield service
    app.dependency_overrides.clear()
    
@pytest.fixture
def admin_viewer(client, current_user):
    """공개 조회를 관리자 눈으로 본다 (옵셔널 인증 override)"""
    current_user.grant_all()      # can_manage_post 포함
    app.dependency_overrides[get_current_user_optional] = lambda: current_user
    yield client
    app.dependency_overrides.clear()
    
@pytest.fixture
def admin_viewer(client, current_user):
    """공개 조회(get_current_user_optional)를 관리자 눈으로 본다"""
    current_user.grant_all()      # can_manage_post 포함
    app.dependency_overrides[get_current_user_optional] = lambda: current_user
    yield client
    app.dependency_overrides.pop(get_current_user_optional, None)