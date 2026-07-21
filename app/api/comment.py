#app/api/comment.py

'''
2026-07-21
댓글 관련 라우터 (생성, 수정, 삭제)
'''

from fastapi import APIRouter, Depends, HTTPException, Body
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from sqlalchemy import select
from ..database.connection import get_db
from ..database.orm import Post, Comment
from ..schema.request import CommentCreate
from ..schema.response import PostDetailSchema

router = APIRouter(tags=["comment"])


@router.post("/page/{post_id}/comment", status_code=201, response_model=PostDetailSchema)#댓글 쓰기
def create_comment_handler(
    post_id: int,
    request: CommentCreate,
    session: Session = Depends(get_db),
):
    post = session.scalar(
        select(Post).where(Post.id == post_id).where(Post.is_deleted == False)
    )
    if post is None:
        raise HTTPException(status_code=404, detail="post not found")

    comment = Comment.create(request=request, post_id=post_id)
    session.add(comment)
    session.commit()
    session.refresh(post)

    post.comments = [c for c in post.comments if not c.is_deleted]
    return post


@router.patch("/comment/{id}", status_code=200)#댓글 수정
def update_comment_handler(
    id: int,
    contents: str = Body(..., embed=True),
    session: Session = Depends(get_db),
):
    comment = session.scalar(
        select(Comment).where(Comment.id == id).where(Comment.is_deleted == False)
    )
    if comment is None:
        raise HTTPException(status_code=404, detail="comment not found")

    comment.contents = contents
    comment.updated_at = datetime.now(timezone.utc)
    session.commit()
    session.refresh(comment)
    return comment


@router.delete("/comment/{id}", status_code=204)#댓글 삭제
def delete_comment_handler(
    id: int,
    session: Session = Depends(get_db),
):
    comment = session.scalar(
        select(Comment).where(Comment.id == id).where(Comment.is_deleted == False)
    )
    if comment is None:
        raise HTTPException(status_code=404, detail="comment not found")

    comment.is_deleted = True
    comment.updated_at = datetime.now(timezone.utc)
    session.commit()
    return