#app/tests/test_post.py

'''
2026-07-21
글 API 테스트

2026-07-23
인증/권한 반영

2026-07-24
분류 반영 / 이미지 제거 / 썸네일
권한 체크박스 반영

2026-07-28
게시글 수정 입력 검증
'''

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.database.orm import Post, User, Category
from app.schema.request import PostCreate, PostUpdate


def _make_user(id=1, nickname="tester"):
    return User(
        id=id, email=f"{nickname}@example.com", password="hash",
        nickname=nickname, is_verified=True,
        can_comment=True, can_write_post=True, can_upload=True,
        can_manage_category=True, can_manage_user=True,
        suspended_until=None, is_banned=False,
        created_at=datetime(2026, 7, 23, tzinfo=timezone.utc),
    )


def _make_category(id=1, slug="dnd", name="TRPG"):
    return Category(id=id, slug=slug, name=name, display_order=0)


def _make_post(id=1, title="테스트 글", contents="본문", user_id=1, nickname="tester", thumbnail_url=None):
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
        view_count=0,
    )
    # mock 으로 만든 객체는 DB를 거치지 않으므로 관계를 직접 채운다
    post.user = _make_user(id=user_id, nickname=nickname)
    post.category = _make_category()
    post.comments = []
    return post


def _make_post_request(**overrides):
    """PostCreate 스키마 검증용 요청 객체 생성 헬퍼"""
    data = {
        "title": "제목",
        "contents": "본문",
        "category_id": 1,
    }
    data.update(overrides)
    return PostCreate(**data)


def _make_post_update(**overrides):
    """PostUpdate 스키마 검증용 요청 객체 생성 헬퍼"""
    return PostUpdate(**overrides)


# ---------- 목록 조회 ----------

def test_get_pages(client, mock_post_repo, mock_category_repo, mock_like_repo):
    mock_post_repo.get_posts.return_value = [_make_post(thumbnail_url="/img/a.png")]
    mock_post_repo.count_comments.return_value = 2
    mock_like_repo.count_for_post.return_value = 5
    
    response = client.get("/pages")

    assert response.status_code == 200
    data = response.json()
    assert len(data["posts"]) == 1
    assert data["posts"][0]["title"] == "테스트 글"
    assert data["posts"][0]["user"]["nickname"] == "tester"
    assert data["posts"][0]["category"]["slug"] == "dnd"
    assert data["posts"][0]["thumbnail_url"] == "/img/a.png"
    assert data["posts"][0]["comment_count"] == 2
    assert data["posts"][0]["like_count"] == 5
    assert data["posts"][0]["view_count"] == 0


def test_get_pages_without_thumbnail(client, mock_post_repo, mock_category_repo, mock_like_repo):
    """이미지 없는 글은 썸네일이 null"""
    mock_post_repo.get_posts.return_value = [_make_post()]
    mock_post_repo.count_comments.return_value = 0
    mock_like_repo.count_for_post.return_value = 0

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

    mock_post_repo.get_posts.assert_called_once_with(order="asc", category_id=None, user_id=None, include_deleted=False)


def test_get_pages_filtered_by_category(client, mock_post_repo, mock_category_repo):
    mock_category_repo.get_category_by_slug.return_value = _make_category(id=7)
    mock_post_repo.get_posts.return_value = []

    response = client.get("/pages?category=dnd&order=desc")

    assert response.status_code == 200
    mock_post_repo.get_posts.assert_called_once_with(order="desc", category_id=7, user_id=None, include_deleted=False)


def test_get_pages_unknown_category(client, mock_post_repo, mock_category_repo):
    mock_category_repo.get_category_by_slug.return_value = None

    response = client.get("/pages?category=nope")

    assert response.status_code == 404
    mock_post_repo.get_posts.assert_not_called()


# ---------- 단일 조회 ----------

def test_get_page(client, mock_post_repo, mock_redis):
    post = _make_post()
    mock_post_repo.get_post_by_id.return_value = _make_post()
    mock_redis.set.return_value = True
    mock_post_repo.increment_view_count.return_value = 1

    response = client.get("/page/1")

    assert response.status_code == 200
    data = response.json()
    assert data["id"] == 1
    assert data["title"] == "테스트 글"
    assert data["category"]["name"] == "TRPG"
    assert data["comments"] == []
    mock_redis.set.assert_awaited_once()


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


def test_create_post_without_permission(auth_client, mock_post_repo, mock_category_repo):
    """댓글만 가능한 회원은 글을 쓸 수 없다"""
    response = auth_client.post(
        "/page", json={"title": "글", "contents": "본문", "category_id": 1}
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "permission denied: can_write_post"
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


# ---------- 생성 요청값 검증 ----------

def test_post_create_accepts_title_boundaries():
    """제목은 공백 제거 후 1자부터 200자까지 허용한다"""
    assert _make_post_request(title="a").title == "a"
    assert len(_make_post_request(title="a" * 200).title) == 200


def test_post_create_rejects_title_over_200():
    """제목이 200자를 넘으면 거부한다"""
    with pytest.raises(ValidationError):
        _make_post_request(title="a" * 201)


def test_post_create_strips_title_edges():
    """제목 앞뒤 공백은 저장 전에 제거한다"""
    assert _make_post_request(title="  제목  ").title == "제목"


def test_post_create_rejects_blank_title():
    """공백만 있는 제목은 거부한다"""
    with pytest.raises(ValidationError):
        _make_post_request(title="   ")


def test_post_create_accepts_contents_boundaries():
    """본문은 1자부터 100,000자까지 허용한다"""
    assert _make_post_request(contents="a").contents == "a"
    assert len(_make_post_request(contents="a" * 100_000).contents) == 100_000


def test_post_create_rejects_contents_over_100000():
    """본문이 100,000자를 넘으면 거부한다"""
    with pytest.raises(ValidationError):
        _make_post_request(contents="a" * 100_001)


def test_post_create_rejects_blank_contents():
    """공백 문자만 있는 본문은 거부한다"""
    with pytest.raises(ValidationError):
        _make_post_request(contents=" \n\t ")


# ---------- 수정 ----------

def test_update_post(auth_client, mock_post_repo):
    """권한이 없어도 이미 쓴 자기 글은 고칠 수 있다"""
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


def test_update_post_when_suspended(suspended_client, mock_post_repo):
    """제재 중엔 새 내용을 만들 수 없다"""
    mock_post_repo.get_post_by_id.return_value = _make_post(user_id=1)

    response = suspended_client.patch("/page/1", json={"title": "수정"})

    assert response.status_code == 403
    assert response.json()["detail"] == "suspended"
    mock_post_repo.update.assert_not_called()


def test_update_post_not_found(auth_client, mock_post_repo):
    mock_post_repo.get_post_by_id.return_value = None

    response = auth_client.patch("/page/999", json={"title": "수정"})

    assert response.status_code == 404



def test_post_update_accepts_boundaries():
    """수정도 생성과 같은 길이 경계를 허용한다."""
    assert _make_post_update(title="a").title == "a"
    assert len(_make_post_update(title="a" * 200).title) == 200
    assert _make_post_update(contents="a").contents == "a"
    assert len(_make_post_update(contents="a" * 100_000).contents) == 100_000


def test_post_update_strips_title_edges():
    """수정 제목도 앞뒤 공백을 제거한다."""
    assert _make_post_update(title="  수정 제목  ").title == "수정 제목"


@pytest.mark.parametrize(
    "payload",
    [
        {"title": "   "},
        {"title": "a" * 201},
        {"contents": " \n\t "},
        {"contents": "a" * 100_001},
    ],
)
def test_update_post_rejects_invalid_payload(
    auth_client,
    mock_post_repo,
    payload,
):
    response = auth_client.patch("/page/1", json=payload)

    assert response.status_code == 422
    mock_post_repo.get_post_by_id.assert_not_called()
    mock_post_repo.update.assert_not_called()


# ---------- 삭제 ----------

def test_delete_post(auth_client, mock_post_repo):
    post = _make_post(user_id=1)
    mock_post_repo.get_post_by_id.return_value = post

    response = auth_client.delete("/page/1")

    assert response.status_code == 204
    assert post.is_deleted is True          # 소프트삭제 표시됐나
    mock_post_repo.update.assert_called_once()


def test_delete_post_when_banned(banned_client, mock_post_repo):
    """지우는 건 제재 중에도 허용한다"""
    post = _make_post(user_id=1)
    mock_post_repo.get_post_by_id.return_value = post

    response = banned_client.delete("/page/1")

    assert response.status_code == 204
    assert post.is_deleted is True


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
    
def test_admin_sees_deleted_posts_in_list(admin_viewer, mock_post_repo, mock_category_repo):
    """관리자는 삭제된 글도 목록에서 본다"""
    mock_post_repo.get_posts.return_value = []
    admin_viewer.get("/pages?order=desc")
    mock_post_repo.get_posts.assert_called_once_with(
        order="desc", category_id=None, user_id=None, include_deleted=True
    )


def test_anonymous_does_not_see_deleted_posts(client, mock_post_repo, mock_category_repo):
    mock_post_repo.get_posts.return_value = []
    client.get("/pages?order=desc")
    mock_post_repo.get_posts.assert_called_once_with(
        order="desc", category_id=None, user_id=None, include_deleted=False
    )


def test_admin_can_open_deleted_post(admin_viewer, mock_post_repo):
    post = _make_post(user_id=99, nickname="other")
    post.is_deleted = True
    mock_post_repo.get_post_by_id.return_value = post

    response = admin_viewer.get("/page/1")

    assert response.status_code == 200
    assert response.json()["is_deleted"] is True
    mock_post_repo.get_post_by_id.assert_called_once_with(1, include_deleted=True)


def test_anonymous_cannot_open_deleted_post(client, mock_post_repo):
    """익명에겐 삭제 글이 안 잡혀서 404"""
    mock_post_repo.get_post_by_id.return_value = None
    response = client.get("/page/1")

    assert response.status_code == 404
    mock_post_repo.get_post_by_id.assert_called_once_with(1, include_deleted=False)
    
def test_restore_post(admin_client, mock_post_repo):
    """관리자가 삭제된 글을 되살린다"""
    post = _make_post(user_id=99, nickname="other")
    post.is_deleted = True
    mock_post_repo.get_post_by_id.return_value = post
    mock_post_repo.update.return_value = post

    response = admin_client.post("/page/1/restore")

    assert response.status_code == 200
    assert post.is_deleted is False
    # 삭제된 글을 찾아야 하므로 include_deleted=True 로 조회
    mock_post_repo.get_post_by_id.assert_called_once_with(1, include_deleted=True)
    mock_post_repo.update.assert_called_once()


def test_restore_post_without_permission(auth_client, mock_post_repo):
    """글 관리 권한이 없으면 복구 불가"""
    response = auth_client.post("/page/1/restore")

    assert response.status_code == 403
    assert response.json()["detail"] == "permission denied: can_manage_post"
    mock_post_repo.update.assert_not_called()


def test_restore_post_without_token(client, mock_post_repo):
    response = client.post("/page/1/restore")

    assert response.status_code == 401
    mock_post_repo.update.assert_not_called()


def test_restore_post_not_found(admin_client, mock_post_repo):
    mock_post_repo.get_post_by_id.return_value = None

    response = admin_client.post("/page/999/restore")

    assert response.status_code == 404
    
# ---------- 조회수 ----------

def test_view_count_increments_on_first_view(client, mock_post_repo, mock_redis):
    """처음 보는 IP면 조회수 +1"""
    post = _make_post(user_id=1)
    mock_post_repo.get_post_by_id.return_value = post
    mock_redis.set.return_value = True                    # Redis에 키 없음 = 첫 조회
    mock_post_repo.increment_view_count.return_value = 6

    response = client.get("/page/1")

    assert response.status_code == 200
    assert response.json()["view_count"] == 6
    mock_post_repo.increment_view_count.assert_called_once_with(1)
    mock_redis.set.assert_awaited_once()


def test_view_count_dedup_same_ip(client, mock_post_repo, mock_redis):
    """이미 본 IP면 조회수를 올리지 않는다"""
    post = _make_post(user_id=1)
    mock_post_repo.get_post_by_id.return_value = post
    mock_redis.set.return_value = None                    # 키가 이미 있음 = 재조회

    response = client.get("/page/1")

    assert response.status_code == 200
    mock_post_repo.increment_view_count.assert_not_called()
    mock_redis.set.assert_awaited_once()


def test_view_count_skipped_for_deleted_post(admin_viewer, mock_post_repo):
    """삭제된 글(관리자만 봄)은 조회수를 세지 않는다"""
    post = _make_post(user_id=99, nickname="other")
    post.is_deleted = True
    mock_post_repo.get_post_by_id.return_value = post

    response = admin_viewer.get("/page/1")

    assert response.status_code == 200
    mock_post_repo.increment_view_count.assert_not_called()
    
# ---------- 좋아요 ----------

def test_like_first_time(auth_client, mock_post_repo, mock_like_repo):
    """처음 누르면 좋아요 (add 호출, liked=True)"""
    mock_post_repo.get_post_by_id.return_value = _make_post()
    mock_like_repo.exists.return_value = False        # 아직 안 누름
    mock_like_repo.count_for_post.return_value = 1

    response = auth_client.post("/page/1/like")

    assert response.status_code == 200
    body = response.json()
    assert body["liked"] is True
    assert body["like_count"] == 1
    mock_like_repo.add.assert_called_once()
    mock_like_repo.remove.assert_not_called()


def test_like_toggle_off(auth_client, mock_post_repo, mock_like_repo):
    """이미 눌렀으면 한 번 더 = 취소 (remove 호출, liked=False)"""
    mock_post_repo.get_post_by_id.return_value = _make_post()
    mock_like_repo.exists.return_value = True          # 이미 누름
    mock_like_repo.count_for_post.return_value = 0

    response = auth_client.post("/page/1/like")

    assert response.status_code == 200
    body = response.json()
    assert body["liked"] is False
    assert body["like_count"] == 0
    mock_like_repo.remove.assert_called_once()
    mock_like_repo.add.assert_not_called()


def test_like_requires_login(client, mock_post_repo, mock_like_repo):
    """비로그인은 좋아요 못 누른다"""
    response = client.post("/page/1/like")

    assert response.status_code == 401
    mock_like_repo.add.assert_not_called()


def test_like_blocked_when_banned(banned_client, mock_post_repo, mock_like_repo):
    """제재(강퇴) 중엔 좋아요 못 누른다"""
    response = banned_client.post("/page/1/like")

    assert response.status_code == 403
    mock_like_repo.add.assert_not_called()


def test_like_post_not_found(auth_client, mock_post_repo, mock_like_repo):
    mock_post_repo.get_post_by_id.return_value = None

    response = auth_client.post("/page/999/like")

    assert response.status_code == 404
    mock_like_repo.add.assert_not_called()


def test_get_like_status_anonymous(client, mock_post_repo, mock_like_repo):
    """비로그인은 liked=False, 좋아요 수는 보인다"""
    mock_post_repo.get_post_by_id.return_value = _make_post()
    mock_like_repo.count_for_post.return_value = 3

    response = client.get("/page/1/like")

    assert response.status_code == 200
    body = response.json()
    assert body["liked"] is False
    assert body["like_count"] == 3


def test_get_like_status_when_liked(admin_viewer, mock_post_repo, mock_like_repo):
    """내가 누른 글이면 liked=True (옵셔널 인증이라 admin_viewer 사용)"""
    mock_post_repo.get_post_by_id.return_value = _make_post()
    mock_like_repo.exists.return_value = True
    mock_like_repo.count_for_post.return_value = 5

    response = admin_viewer.get("/page/1/like")

    assert response.status_code == 200
    body = response.json()
    assert body["liked"] is True
    assert body["like_count"] == 5