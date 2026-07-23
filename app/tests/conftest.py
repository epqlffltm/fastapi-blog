#app/tests/conftest.py

'''
2026-07-21
테스트 공통 fixture

2026-07-23
인증 fixture 추가
'''

import pytest
from datetime import datetime, timezone
from fastapi.testclient import TestClient
from unittest.mock import Mock
from app.main import app
from app.database.orm import User
from app.database.repository import PostRepository, CommentRepository, UserRepository
from app.api.dependency import get_current_user
from redis import Redis
from app.database.cache import get_redis_client


@pytest.fixture
def client():
    return TestClient(app=app)


@pytest.fixture
def current_user():
    return User(
        id=1,
        email="test@example.com",
        password="$2b$12$fakehashedpassword",
        nickname="tester",
        is_verified=False,
        created_at=datetime(2026, 7, 23, tzinfo=timezone.utc),
    )


@pytest.fixture
def auth_client(client, current_user):
    """로그인된 상태의 클라이언트 (get_current_user를 고정 유저로 교체)"""
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
def mock_redis():
    redis = Mock(spec=Redis)
    app.dependency_overrides[get_redis_client] = lambda: redis
    yield redis
    app.dependency_overrides.clear()