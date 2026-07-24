#app/tests/test_post.py

'''
2026-07-21
글 API 테스트

2026-07-23
인증/권한 반영

2026-07-24
분류 반영
이미지 제거 / 썸네일 반영
글 작성은 관리자만
'''

from datetime import datetime, timezone
from app.database.orm import Post, User, Category, UserRole


def _make_user(id=1, nickname="tester"):
    return User(
        id=id, email=f"{nickname}@example.com", password="hash",
        nickname=nickname, is_verified=True, role=UserRole.ADMIN,
        created_at=datetime(2026, 7, 23, tzinfo=timezone.utc),
    )


def _make_category(id=1, slug="dnd", name="TRPG"):
    return Category(id=id, slug=slug, name=name, display_order=0)


def _make_post(id=1, title="테스트 글", contents="본문", user_id=1,
               nickname="tester", thumbnail_url=None):
    """테스트용 Post 객체 생성 헬퍼"""
    now = datetime(2026, 7, 21, tzinfo=timezone.utc)
    post = Post(
        id=id,
        title=title,
        contents=contents,
        user_id=user_id,
        category_id=1,
        thumbnail_url=thumbnail_url,
        created_at=now,
        updated_at=now,
        is_deleted=False,
    )
    # mock 으로 만든 객체는 DB를 거치지 않으므로 관계를 직접 채운다
    post.user = _make_user(id=user_id, nickname=nickname)
    post.category = _make_category()
    post.comments = []
    return post


# ---------- 목록 조회 ----------

def test_get_pages(client, mock_post_repo, mock_category_repo):
    mock_post_repo.get_posts.return_value = [_make_post(thumbnail_url="/img/a.png")]
    mock_post_repo.count_comments.return_value = 2

    response = client.get("/pages")

    assert response.status_code == 200
    data = response.json()
    assert len(data["posts"]) == 1
    assert data["posts"][0]["title"] == "테스트 글"
    assert data["posts"][0]["user"]["nickname"] == "tester"
    assert data["posts"][0]["category"]["slug"] == "dnd"
    assert data["posts"][0]["thumbnail_url"] == "/img/a.png"
    assert data["posts"][0]["comment_count"] == 2


def test_get_pages_without_thumbnail(client, mock_post_repo, mock_category_repo):
    """이미지 없는 글은 썸네일이 null"""
    mock_post_repo.get_posts.return_value = [_make_post()]
    mock_post_repo.count_comments.return_value = 0

    response = client.get("/pages")

    assert response.status_code == 200
    assert response.json()["posts"][0]["thumbnail_url"] is None


def test_get_pages_empty(client, mock_post_repo, mock_category_repo):
    mock_post_repo.get_posts.return_value = []

    response = client.get("/pages")

    assert response.status_code == 200
    assert response.json()["posts"] == []


def test_get_pages_order_asc(client, mock_post_repo, mock_category_repo):
    """정렬 파라미터가 repository에 전달되는지"""
    mock_post_repo.get_posts.return_value = []

    client.get("/pages?order=asc")

    mock_post_repo.get_posts.assert_called_once_with(order="asc", category_id=None)


def test_get_pages_filtered_by_category(client, mock_post_repo, mock_category_repo):
    mock_category_repo.get_category_by_slug.return_value = _make_category(id=7)
    mock_post_repo.get_posts.return_value = []

    response = client.get("/pages?category=dnd&order=desc")

    assert response.status_code == 200
    mock_post_repo.get_posts.assert_called_once_with(order="desc", category_id=7)


def test_get_pages_unknown_category(client, mock_post_repo, mock_category_repo):
    mock_category_repo.get_category_by_slug.return_value = None

    response = client.get("/pages?category=nope")

    assert response.status_code == 404
    mock_post_repo.get_posts.assert_not_called()


# ---------- 단일 조회 ----------

def test_get_page(client, mock_post_repo):
    mock_post_repo.get_post_by_id.return_value = _make_post()

    response = client.get("/page/1")

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == 1
    assert data["title"] == "테스트 글"
    assert data["category"]["name"] == "TRPG"
    assert data["comments"] == []


def test_get_page_not_found(client, mock_post_repo):
    """없는 글이면 404"""
    mock_post_repo.get_post_by_id.return_value = None

    response = client.get("/page/999")

    assert response.status_code == 404
    assert response.json()["detail"] == "post not found"


# ---------- 생성 ----------

def test_create_post(admin_client, mock_post_repo, mock_category_repo):
    mock_category_repo.get_category_by_id.return_value = _make_category()
    mock_post_repo.save.return_value = _make_post(id=10, title="새 글")

    response = admin_client.post(
        "/page",
        json={"title": "새 글", "contents": "새 본문", "category_id": 1},
    )

    assert response.status_code == 201
    data = response.json()
    assert data["id"] == 10
    assert data["title"] == "새 글"
    mock_post_repo.save.assert_called_once()


def test_create_post_extracts_thumbnail(admin_client, mock_post_repo, mock_category_repo):
    """본문 첫 이미지가 썸네일로 저장되는지"""
    mock_category_repo.get_category_by_id.return_value = _make_category()
    mock_post_repo.save.return_value = _make_post(id=10)   # 응답 변환용

    admin_client.post(
        "/page",
        json={
            "title": "글",
            "contents": "앞글\n\n![](/img/first.png)\n\n![](/img/second.png)",
            "category_id": 1,
        },
    )

    # 반환값이 아니라 save 에 넘어간 객체를 본다
    saved = mock_post_repo.save.call_args.args[0]
    assert saved.thumbnail_url == "/img/first.png"


def test_create_post_unknown_category(admin_client, mock_post_repo, mock_category_repo):
    mock_category_repo.get_category_by_id.return_value = None

    response = admin_client.post(
        "/page",
        json={"title": "글", "contents": "본문", "category_id": 999},
    )

    assert response.status_code == 400
    mock_post_repo.save.assert_not_called()


def test_create_post_as_member(auth_client, mock_post_repo, mock_category_repo):
    """일반 회원은 글을 쓸 수 없다 (댓글만)"""
    response = auth_client.post(
        "/page", json={"title": "글", "contents": "본문", "category_id": 1}
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "admin only"
    mock_post_repo.save.assert_not_called()


def test_create_post_without_token(client, mock_post_repo, mock_category_repo):
    """로그인 안 하면 글을 쓸 수 없다"""
    response = client.post(
        "/page", json={"title": "글", "contents": "본문", "category_id": 1}
    )

    assert response.status_code == 401
    mock_post_repo.save.assert_not_called()


def test_create_post_missing_field(admin_client, mock_post_repo, mock_category_repo):
    """필수 필드 빠지면 422"""
    response = admin_client.post("/page", json={"title": "제목만"})

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


def test_update_post_updates_thumbnail(auth_client, mock_post_repo):
    """본문이 바뀌면 썸네일도 다시 계산된다"""
    post = _make_post(user_id=1, thumbnail_url="/img/old.png")
    mock_post_repo.get_post_by_id.return_value = post
    mock_post_repo.update.return_value = post

    auth_client.patch("/page/1", json={"contents": "![](/img/new.png)"})

    assert post.thumbnail_url == "/img/new.png"


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
    assert post.is_deleted is True          # 소프트삭제 표시됐나
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