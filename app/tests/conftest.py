#app/tests/conftest.py

'''
2026-07-21
testcode코드 작성

2026-07-23
fixture 추가
'''

import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock
from app.main import app
from app.database.repository import PostRepository, CommentRepository, UserRepository



@pytest.fixture
def client():
    return TestClient(app=app)


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