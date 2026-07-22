#app/tests/test_post.py

'''
2026-07-21
글 API 테스트
'''

from datetime import datetime, timezone
from app.database.orm import Post


def _make_post(id=1, title="테스트 글", nickname="hong", contents="본문"):
    """테스트용 Post 객체 생성 헬퍼"""
    now = datetime(2026, 7, 21, tzinfo=timezone.utc)
    post = Post(
        id=id,
        title=title,
        nickname=nickname,
        contents=contents,
        created_at=now,
        updated_at=now,
        is_deleted=False,
    )
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
    assert data["posts"][0]["comment_count"] == 2


def test_get_pages_empty(client, mock_post_repo):
    """글이 하나도 없을 때"""
    mock_post_repo.get_posts.return_value = []

    response = client.get("/pages")

    assert response.status_code == 200
    assert response.json()["posts"] == []


def test_get_pages_order_asc(client, mock_post_repo):
    """정렬 파라미터가 repository에 전달되는지"""
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
    assert data["contents"] == "본문"
    assert data["comments"] == []
    assert data["images"] == []


def test_get_page_not_found(client, mock_post_repo):
    """없는 글이면 404"""
    mock_post_repo.get_post_by_id.return_value = None

    response = client.get("/page/999")

    assert response.status_code == 404
    assert response.json()["detail"] == "post not found"


# ---------- 생성 ----------

def test_create_post(client, mock_post_repo):
    created = _make_post(id=10, title="새 글", nickname="kim", contents="새 본문")
    mock_post_repo.save_with_images.return_value = created

    response = client.post(
        "/page",
        json={
            "title": "새 글",
            "nickname": "kim",
            "contents": "새 본문",
            "image": [],
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert data["id"] == 10
    assert data["title"] == "새 글"
    mock_post_repo.save_with_images.assert_called_once()


def test_create_post_without_image(client, mock_post_repo):
    """image를 안 보내도 글이 만들어지는지 (기본값 [])"""
    mock_post_repo.save_with_images.return_value = _make_post(id=11)

    response = client.post(
        "/page",
        json={"title": "이미지 없는 글", "nickname": "lee", "contents": "본문"},
    )

    assert response.status_code == 201


def test_create_post_missing_field(client, mock_post_repo):
    """필수 필드 빠지면 422"""
    response = client.post("/page", json={"title": "제목만"})

    assert response.status_code == 422


# ---------- 수정 ----------

def test_update_post(client, mock_post_repo):
    post = _make_post()
    mock_post_repo.get_post_by_id.return_value = post
    mock_post_repo.update.return_value = post

    response = client.patch("/page/1", json={"title": "수정된 제목"})

    assert response.status_code == 200
    assert response.json()["title"] == "수정된 제목"
    mock_post_repo.update.assert_called_once()


def test_update_post_not_found(client, mock_post_repo):
    mock_post_repo.get_post_by_id.return_value = None

    response = client.patch("/page/999", json={"title": "수정"})

    assert response.status_code == 404


# ---------- 삭제 ----------

def test_delete_post(client, mock_post_repo):
    post = _make_post()
    mock_post_repo.get_post_by_id.return_value = post

    response = client.delete("/page/1")

    assert response.status_code == 204
    assert post.is_deleted is True          # 소프트삭제 표시됐나
    mock_post_repo.update.assert_called_once()


def test_delete_post_not_found(client, mock_post_repo):
    mock_post_repo.get_post_by_id.return_value = None

    response = client.delete("/page/999")

    assert response.status_code == 404