#app/tests/test_comment.py

'''
2026-07-21
댓글 API 테스트

2026-07-23
인증/권한 반영

'''

from datetime import datetime, timezone
from app.database.orm import Post, Comment, User


def _make_user(id=1, nickname="tester"):
    return User(
        id=id, email=f"{nickname}@example.com", password="hash",
        nickname=nickname, is_verified=False,
        created_at=datetime(2026, 7, 23, tzinfo=timezone.utc),
    )


def _make_post(id=1, user_id=1):
    now = datetime(2026, 7, 21, tzinfo=timezone.utc)
    post = Post(
        id=id, title="글", contents="본문", user_id=user_id,
        created_at=now, updated_at=now, is_deleted=False,
    )
    post.user = _make_user(id=user_id)
    post.comments = []
    post.images = []
    return post


def _make_comment(id=1, post_id=1, user_id=1, contents="댓글 내용"):
    now = datetime(2026, 7, 21, tzinfo=timezone.utc)
    comment = Comment(
        id=id, post_id=post_id, user_id=user_id, contents=contents,
        created_at=now, updated_at=now, is_deleted=False,
    )
    comment.user = _make_user(id=user_id)
    return comment


# ---------- 생성 ----------

def test_create_comment(auth_client, mock_post_repo, mock_comment_repo):
    mock_post_repo.get_post_by_id.return_value = _make_post()
    mock_comment_repo.save.return_value = _make_comment()

    response = auth_client.post("/page/1/comment", json={"contents": "댓글 내용"})

    assert response.status_code == 201
    mock_comment_repo.save.assert_called_once()


def test_create_comment_without_token(client, mock_post_repo, mock_comment_repo):
    response = client.post("/page/1/comment", json={"contents": "댓글"})

    assert response.status_code == 401
    mock_comment_repo.save.assert_not_called()


def test_create_comment_post_not_found(auth_client, mock_post_repo, mock_comment_repo):
    mock_post_repo.get_post_by_id.return_value = None

    response = auth_client.post("/page/999/comment", json={"contents": "댓글"})

    assert response.status_code == 404
    mock_comment_repo.save.assert_not_called()


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
    
    