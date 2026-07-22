#app/api/comment.py

'''
2026-07-21
댓글 관련 라우터 (생성, 수정, 삭제)
repository 패턴 적용
'''

from fastapi import APIRouter, Depends, HTTPException, Body
from datetime import datetime, timezone
from ..database.repository import PostRepository, CommentRepository
from ..database.orm import Comment
from ..schema.request import CommentCreate
from ..schema.response import PostDetailSchema

router = APIRouter(tags=["comment"])


@router.post("/page/{post_id}/comment", status_code=201, response_model=PostDetailSchema)#댓글 쓰기
def create_comment_handler(
    post_id: int,
    request: CommentCreate,
    post_repo: PostRepository = Depends(),
    comment_repo: CommentRepository = Depends(),
):
    post = post_repo.get_post_by_id(post_id)
    if post is None:
        raise HTTPException(status_code=404, detail="post not found")

    comment = Comment.create(request=request, post_id=post_id)
    comment_repo.save(comment)

    # 새 댓글 반영된 글 다시 읽기
    post = post_repo.get_post_by_id(post_id)
    post.comments = [c for c in post.comments if not c.is_deleted]
    return post


@router.patch("/comment/{id}", status_code=200)#댓글 수정
def update_comment_handler(
    id: int,
    contents: str = Body(..., embed=True),
    comment_repo: CommentRepository = Depends(),
):
    comment = comment_repo.get_comment_by_id(id)
    if comment is None:
        raise HTTPException(status_code=404, detail="comment not found")

    comment.contents = contents
    comment.updated_at = datetime.now(timezone.utc)
    comment = comment_repo.update(comment)
    return comment


@router.delete("/comment/{id}", status_code=204)#댓글 삭제
def delete_comment_handler(
    id: int,
    comment_repo: CommentRepository = Depends(),
):
    comment = comment_repo.get_comment_by_id(id)
    if comment is None:
        raise HTTPException(status_code=404, detail="comment not found")

    comment.is_deleted = True
    comment.updated_at = datetime.now(timezone.utc)
    comment_repo.update(comment)
    return