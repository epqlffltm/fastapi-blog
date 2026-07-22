#app/tests/conftest.py

'''
testcode코드 작성
'''

import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock
from app.main import app
from app.database.repository import PostRepository, CommentRepository


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