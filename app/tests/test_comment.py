#app/tests/test_comment.py

'''
2026-07-21
댓글 API 테스트
'''

from datetime import datetime, timezone
from app.database.orm import Post, Comment


def _make_post(id=1):
    now = datetime(2026, 7, 21, tzinfo=timezone.utc)
    post = Post(
        id=id, title="글", nickname="hong", contents="본문",
        created_at=now, updated_at=now, is_deleted=False,
    )
    post.comments = []
    post.images = []
    return post


def _make_comment(id=1, post_id=1, nickname="kim", contents="댓글 내용"):
    now = datetime(2026, 7, 21, tzinfo=timezone.utc)
    return Comment(
        id=id, post_id=post_id, nickname=nickname, contents=contents,
        created_at=now, updated_at=now, is_deleted=False,
    )


# ---------- 생성 ----------

def test_create_comment(client, mock_post_repo, mock_comment_repo):
    post = _make_post()
    mock_post_repo.get_post_by_id.return_value = post
    mock_comment_repo.save.return_value = _make_comment()

    response = client.post(
        "/page/1/comment",
        json={"nickname": "kim", "contents": "댓글 내용"},
    )

    assert response.status_code == 201
    mock_comment_repo.save.assert_called_once()


def test_create_comment_post_not_found(client, mock_post_repo, mock_comment_repo):
    """없는 글에 댓글 달면 404"""
    mock_post_repo.get_post_by_id.return_value = None

    response = client.post(
        "/page/999/comment",
        json={"nickname": "kim", "contents": "댓글"},
    )

    assert response.status_code == 404
    mock_comment_repo.save.assert_not_called()      # 저장 시도조차 안 했나


# ---------- 수정 ----------

def test_update_comment(client, mock_comment_repo):
    comment = _make_comment()
    mock_comment_repo.get_comment_by_id.return_value = comment
    mock_comment_repo.update.return_value = comment

    response = client.patch("/comment/1", json={"contents": "수정된 댓글"})

    assert response.status_code == 200
    assert response.json()["contents"] == "수정된 댓글"


def test_update_comment_not_found(client, mock_comment_repo):
    mock_comment_repo.get_comment_by_id.return_value = None

    response = client.patch("/comment/999", json={"contents": "수정"})

    assert response.status_code == 404


# ---------- 삭제 ----------

def test_delete_comment(client, mock_comment_repo):
    comment = _make_comment()
    mock_comment_repo.get_comment_by_id.return_value = comment

    response = client.delete("/comment/1")

    assert response.status_code == 204
    assert comment.is_deleted is True
    mock_comment_repo.update.assert_called_once()


def test_delete_comment_not_found(client, mock_comment_repo):
    mock_comment_repo.get_comment_by_id.return_value = None

    response = client.delete("/comment/999")

    assert response.status_code == 404