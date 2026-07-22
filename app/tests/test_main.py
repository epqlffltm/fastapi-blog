#app/tests/test_main.py

'''
testcode코드 작성
'''

from datetime import datetime, timezone
from app.database.orm import Post


def test_health_check(client):
    response = client.get('/')
    assert response.status_code == 200
    assert response.json() == {"message": "Hello, FastAPI"}


def test_get_pages_handler(client, mock_post_repo):
    # 가짜가 이 글을 준다고 설정
    mock_post_repo.get_posts.return_value = [
        Post(id=1, title="테스트 글", nickname="hong", contents="본문",
            created_at=datetime(2026, 7, 21, tzinfo=timezone.utc),
            updated_at=datetime(2026, 7, 21, tzinfo=timezone.utc),
            is_deleted=False)
    ]
    mock_post_repo.count_comments.return_value = 2

    response = client.get("/pages")

    assert response.status_code == 200
    data = response.json()
    assert len(data["posts"]) == 1
    assert data["posts"][0]["title"] == "테스트 글"
    assert data["posts"][0]["comment_count"] == 2