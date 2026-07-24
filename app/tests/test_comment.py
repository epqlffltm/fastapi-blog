#app/tests/test_comment.py

'''
2026-07-21
댓글 API 테스트

2026-07-23
인증/권한 반영

2026-07-24
분류 반영 / 이미지 제거
대댓글 (1단계) 및 삭제 자리표시자
등급 반영
'''

from datetime import datetime, timedelta, timezone
from app.database.orm import Post, Comment, User, Category, UserRole
from app.service.comment import visible_comments

BASE = datetime(2026, 7, 21, tzinfo=timezone.utc)


def _make_user(id=1, nickname="tester"):
    return User(
        id=id, email=f"{nickname}@example.com", password="hash",
        nickname=nickname, is_verified=True, role=UserRole.MEMBER,
        created_at=datetime(2026, 7, 23, tzinfo=timezone.utc),
    )


def _make_post(id=1, user_id=1):
    post = Post(
        id=id, title="글", contents="본문", user_id=user_id, category_id=1,
        thumbnail_url=None, created_at=BASE, updated_at=BASE, is_deleted=False,
    )
    post.user = _make_user(id=user_id)
    post.category = Category(id=1, slug="dnd", name="TRPG", display_order=0)
    post.comments = []
    return post


def _make_comment(id=1, post_id=1, user_id=1, contents="댓글 내용",
                  parent_id=None, is_deleted=False, minutes=0):
    comment = Comment(
        id=id, post_id=post_id, user_id=user_id, contents=contents,
        parent_id=parent_id, is_deleted=is_deleted,
        created_at=BASE + timedelta(minutes=minutes),
        updated_at=BASE + timedelta(minutes=minutes),
    )
    comment.user = _make_user(id=user_id)
    return comment


# ---------- 생성 ----------

def test_create_comment(auth_client, mock_post_repo, mock_comment_repo):
    """일반 회원도 댓글은 쓸 수 있다"""
    mock_post_repo.get_post_by_id.return_value = _make_post()
    mock_comment_repo.save.return_value = _make_comment()

    response = auth_client.post("/page/1/comment", json={"contents": "댓글 내용"})

    assert response.status_code == 201
    mock_comment_repo.save.assert_called_once()
    saved = mock_comment_repo.save.call_args.args[0]
    assert saved.parent_id is None          # 기본은 원댓글


def test_create_reply(auth_client, mock_post_repo, mock_comment_repo):
    mock_post_repo.get_post_by_id.return_value = _make_post()
    mock_comment_repo.get_comment_by_id.return_value = _make_comment(id=5)

    response = auth_client.post(
        "/page/1/comment", json={"contents": "답글", "parent_id": 5}
    )

    assert response.status_code == 201
    saved = mock_comment_repo.save.call_args.args[0]
    assert saved.parent_id == 5


def test_create_reply_to_reply(auth_client, mock_post_repo, mock_comment_repo):
    """답글의 답글은 받지 않는다 (깊이 1)"""
    mock_post_repo.get_post_by_id.return_value = _make_post()
    mock_comment_repo.get_comment_by_id.return_value = _make_comment(id=5, parent_id=3)

    response = auth_client.post(
        "/page/1/comment", json={"contents": "답글의 답글", "parent_id": 5}
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "cannot reply to a reply"
    mock_comment_repo.save.assert_not_called()


def test_create_reply_parent_not_found(auth_client, mock_post_repo, mock_comment_repo):
    mock_post_repo.get_post_by_id.return_value = _make_post()
    mock_comment_repo.get_comment_by_id.return_value = None

    response = auth_client.post(
        "/page/1/comment", json={"contents": "답글", "parent_id": 999}
    )

    assert response.status_code == 400
    mock_comment_repo.save.assert_not_called()


def test_create_reply_parent_on_other_post(auth_client, mock_post_repo, mock_comment_repo):
    """다른 글의 댓글에는 답글을 달 수 없다"""
    mock_post_repo.get_post_by_id.return_value = _make_post(id=1)
    mock_comment_repo.get_comment_by_id.return_value = _make_comment(id=5, post_id=2)

    response = auth_client.post(
        "/page/1/comment", json={"contents": "답글", "parent_id": 5}
    )

    assert response.status_code == 400
    mock_comment_repo.save.assert_not_called()


def test_create_comment_without_token(client, mock_post_repo, mock_comment_repo):
    response = client.post("/page/1/comment", json={"contents": "댓글"})

    assert response.status_code == 401
    mock_comment_repo.save.assert_not_called()


def test_create_comment_post_not_found(auth_client, mock_post_repo, mock_comment_repo):
    """없는 글에 댓글 달면 404"""
    mock_post_repo.get_post_by_id.return_value = None

    response = auth_client.post("/page/999/comment", json={"contents": "댓글"})

    assert response.status_code == 404
    mock_comment_repo.save.assert_not_called()      # 저장 시도조차 안 했나


# ---------- 수정 ----------

def test_update_comment(auth_client, mock_comment_repo):
    comment = _make_comment(user_id=1)
    mock_comment_repo.get_comment_by_id.return_value = comment
    mock_comment_repo.update.return_value = comment

    response = auth_client.patch("/comment/1", json={"contents": "수정된 댓글"})

    assert response.status_code == 200
    assert response.json()["contents"] == "수정된 댓글"


def test_update_comment_not_mine(auth_client, mock_comment_repo):
    mock_comment_repo.get_comment_by_id.return_value = _make_comment(user_id=99)

    response = auth_client.patch("/comment/1", json={"contents": "수정"})

    assert response.status_code == 403
    assert response.json()["detail"] == "not your comment"
    mock_comment_repo.update.assert_not_called()


def test_update_comment_not_found(auth_client, mock_comment_repo):
    mock_comment_repo.get_comment_by_id.return_value = None

    response = auth_client.patch("/comment/999", json={"contents": "수정"})

    assert response.status_code == 404


# ---------- 삭제 ----------

def test_delete_comment(auth_client, mock_comment_repo):
    comment = _make_comment(user_id=1)
    mock_comment_repo.get_comment_by_id.return_value = comment

    response = auth_client.delete("/comment/1")

    assert response.status_code == 204
    assert comment.is_deleted is True
    mock_comment_repo.update.assert_called_once()


def test_delete_comment_not_mine(auth_client, mock_comment_repo):
    comment = _make_comment(user_id=99)
    mock_comment_repo.get_comment_by_id.return_value = comment

    response = auth_client.delete("/comment/1")

    assert response.status_code == 403
    assert comment.is_deleted is False


def test_delete_comment_not_found(auth_client, mock_comment_repo):
    mock_comment_repo.get_comment_by_id.return_value = None

    response = auth_client.delete("/comment/999")

    assert response.status_code == 404


# ---------- 표시 규칙 ----------

def test_visible_keeps_alive_comments():
    comments = [_make_comment(id=1), _make_comment(id=2, parent_id=1, minutes=1)]

    assert [c.id for c in visible_comments(comments)] == [1, 2]


def test_visible_drops_deleted_reply():
    """삭제된 답글은 남길 이유가 없다"""
    comments = [
        _make_comment(id=1),
        _make_comment(id=2, parent_id=1, is_deleted=True, minutes=1),
    ]

    assert [c.id for c in visible_comments(comments)] == [1]


def test_visible_drops_deleted_comment_without_replies():
    comments = [_make_comment(id=1, is_deleted=True)]

    assert visible_comments(comments) == []


def test_visible_keeps_deleted_parent_with_alive_reply():
    """답글이 남아 있으면 부모는 자리표시자로 남는다"""
    comments = [
        _make_comment(id=1, is_deleted=True),
        _make_comment(id=2, parent_id=1, minutes=1),
    ]

    assert [c.id for c in visible_comments(comments)] == [1, 2]


def test_visible_drops_deleted_parent_when_replies_also_deleted():
    comments = [
        _make_comment(id=1, is_deleted=True),
        _make_comment(id=2, parent_id=1, is_deleted=True, minutes=1),
    ]

    assert visible_comments(comments) == []


def test_visible_sorts_by_time():
    comments = [
        _make_comment(id=3, minutes=20),
        _make_comment(id=1, minutes=0),
        _make_comment(id=2, minutes=10),
    ]

    assert [c.id for c in visible_comments(comments)] == [1, 2, 3]


# ---------- 자리표시자 응답 ----------

def test_deleted_comment_hides_contents(client, mock_post_repo):
    """삭제된 댓글의 내용과 작성자는 응답에 담기지 않는다"""
    post = _make_post()
    post.comments = [
        _make_comment(id=1, contents="지워진 내용", is_deleted=True),
        _make_comment(id=2, parent_id=1, contents="답글", minutes=1),
    ]
    mock_post_repo.get_post_by_id.return_value = post

    response = client.get("/page/1")

    assert response.status_code == 200
    comments = response.json()["comments"]
    assert comments[0]["is_deleted"] is True
    assert comments[0]["contents"] == ""
    assert comments[0]["user"] is None
    assert "지워진 내용" not in response.text
    assert comments[1]["contents"] == "답글"      # 답글은 그대로 보인다