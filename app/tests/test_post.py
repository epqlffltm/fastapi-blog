#app/tests/test_post.py

'''
2026-07-21
글 API 테스트

2026-07-23
인증/권한 반영
'''

from datetime import datetime, timezone
from app.database.orm import Post, User


def _make_user(id=1, nickname="tester"):
    return User(
        id=id, email=f"{nickname}@example.com", password="hash",
        nickname=nickname, is_verified=False,
        created_at=datetime(2026, 7, 23, tzinfo=timezone.utc),
    )


def _make_post(id=1, title="테스트 글", contents="본문", user_id=1, nickname="tester"):
    """테스트용 Post 객체 생성 헬퍼"""
    now = datetime(2026, 7, 21, tzinfo=timezone.utc)
    post = Post(
        id=id,
        title=title,
        contents=contents,
        user_id=user_id,
        created_at=now,
        updated_at=now,
        is_deleted=False,
    )
    post.user = _make_user(id=user_id, nickname=nickname)
    post.comments = []
    post.images = []
    return post


# ---------- 목록 조회 ----------

def test_get_pages(client, mock_post_repo):
    mock_post_repo.get_posts.return_value = [_make_post()]
    mock_post_repo.count_comments.return_value = 2

    response = client.get("/pages")

    assert response.status_code == 200
    data = response.json()
    assert len(data["posts"]) == 1
    assert data["posts"][0]["title"] == "테스트 글"
    assert data["posts"][0]["user"]["nickname"] == "tester"
    assert data["posts"][0]["comment_count"] == 2


def test_get_pages_empty(client, mock_post_repo):
    mock_post_repo.get_posts.return_value = []

    response = client.get("/pages")

    assert response.status_code == 200
    assert response.json()["posts"] == []


def test_get_pages_order_asc(client, mock_post_repo):
    mock_post_repo.get_posts.return_value = []

    client.get("/pages?order=asc")

    mock_post_repo.get_posts.assert_called_once_with(order="asc")


# ---------- 단일 조회 ----------

def test_get_page(client, mock_post_repo):
    mock_post_repo.get_post_by_id.return_value = _make_post()

    response = client.get("/page/1")

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == 1
    assert data["title"] == "테스트 글"
    assert data["user"]["nickname"] == "tester"
    assert data["comments"] == []
    assert data["images"] == []


def test_get_page_not_found(client, mock_post_repo):
    mock_post_repo.get_post_by_id.return_value = None

    response = client.get("/page/999")

    assert response.status_code == 404
    assert response.json()["detail"] == "post not found"


# ---------- 생성 ----------

def test_create_post(auth_client, mock_post_repo):
    mock_post_repo.save_with_images.return_value = _make_post(id=10, title="새 글")

    response = auth_client.post(
        "/page",
        json={"title": "새 글", "contents": "새 본문", "image": []},
    )

    assert response.status_code == 201
    data = response.json()
    assert data["id"] == 10
    assert data["title"] == "새 글"
    mock_post_repo.save_with_images.assert_called_once()


def test_create_post_without_image(auth_client, mock_post_repo):
    mock_post_repo.save_with_images.return_value = _make_post(id=11)

    response = auth_client.post(
        "/page",
        json={"title": "이미지 없는 글", "contents": "본문"},
    )

    assert response.status_code == 201


def test_create_post_without_token(client, mock_post_repo):
    """로그인 안 하면 글을 쓸 수 없다"""
    response = client.post("/page", json={"title": "글", "contents": "본문"})

    assert response.status_code == 401
    mock_post_repo.save_with_images.assert_not_called()


def test_create_post_missing_field(auth_client, mock_post_repo):
    response = auth_client.post("/page", json={"title": "제목만"})

    assert response.status_code == 422


# ---------- 수정 ----------

def test_update_post(auth_client, mock_post_repo):
    post = _make_post(user_id=1)          # 내 글
    mock_post_repo.get_post_by_id.return_value = post
    mock_post_repo.update.return_value = post

    response = auth_client.patch("/page/1", json={"title": "수정된 제목"})

    assert response.status_code == 200
    assert response.json()["title"] == "수정된 제목"
    mock_post_repo.update.assert_called_once()


def test_update_post_not_mine(auth_client, mock_post_repo):
    """남의 글은 수정할 수 없다"""
    mock_post_repo.get_post_by_id.return_value = _make_post(user_id=99, nickname="other")

    response = auth_client.patch("/page/1", json={"title": "수정"})

    assert response.status_code == 403
    assert response.json()["detail"] == "not your post"
    mock_post_repo.update.assert_not_called()


def test_update_post_not_found(auth_client, mock_post_repo):
    mock_post_repo.get_post_by_id.return_value = None

    response = auth_client.patch("/page/999", json={"title": "수정"})

    assert response.status_code == 404


# ---------- 삭제 ----------

def test_delete_post(auth_client, mock_post_repo):
    post = _make_post(user_id=1)
    mock_post_repo.get_post_by_id.return_value = post

    response = auth_client.delete("/page/1")

    assert response.status_code == 204
    assert post.is_deleted is True
    mock_post_repo.update.assert_called_once()


def test_delete_post_not_mine(auth_client, mock_post_repo):
    post = _make_post(user_id=99, nickname="other")
    mock_post_repo.get_post_by_id.return_value = post

    response = auth_client.delete("/page/1")

    assert response.status_code == 403
    assert post.is_deleted is False
    mock_post_repo.update.assert_not_called()


def test_delete_post_not_found(auth_client, mock_post_repo):
    mock_post_repo.get_post_by_id.return_value = None

    response = auth_client.delete("/page/999")

    assert response.status_code == 404