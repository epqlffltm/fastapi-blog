#app/api/post.py

'''
2026-07-21
글 관련 라우터 (목록, 상세, 생성, 수정, 삭제)
'''

from fastapi import APIRouter, Depends, HTTPException, Body
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import select, func
from ..database.connection import get_db
from ..database.orm import Post, Comment, Image
from ..schema.request import PostCreate
from ..schema.response import ListPostSchema, PostListItemSchema, PostDetailSchema

router = APIRouter(tags=["post"])


@router.get("/pages", status_code=200, response_model=ListPostSchema)#글 목록 보기
def get_pages_handler(
    order: str = "random",
    session: Session = Depends(get_db),
):
    order = order.lower()

    stmt = select(Post).where(Post.is_deleted == False)
    if order == "asc":
        stmt = stmt.order_by(Post.created_at.asc())
    elif order == "desc":
        stmt = stmt.order_by(Post.created_at.desc())
    else:
        stmt = stmt.order_by(func.random())

    posts = session.scalars(stmt).all()

    result = []
    for post in posts:
        comment_count = session.scalar(
            select(func.count(Comment.id))
            .where(Comment.post_id == post.id)
            .where(Comment.is_deleted == False)
        )
        result.append(
            PostListItemSchema(
                id=post.id,
                title=post.title,
                nickname=post.nickname,
                created_at=post.created_at,
                comment_count=comment_count,
            )
        )

    return ListPostSchema(posts=result)


@router.get("/page/{id}", status_code=200, response_model=PostDetailSchema)#글 읽기
def get_page_handler(
    id: int,
    session: Session = Depends(get_db),
):
    post = session.scalar(
        select(Post).where(Post.id == id).where(Post.is_deleted == False)
    )
    if post is None:
        raise HTTPException(status_code=404, detail="post not found")

    post.comments = [c for c in post.comments if not c.is_deleted]
    return post


@router.post("/page", status_code=201, response_model=PostDetailSchema)#본문 쓰기
def create_post_handler(
    request: PostCreate,
    session: Session = Depends(get_db),
):
    post = Post.create(request=request)
    session.add(post)
    session.flush()

    for order, url in enumerate(request.image):
        image = Image.create(url=url, post_id=post.id, display_order=order)
        session.add(image)

    session.commit()
    session.refresh(post)
    return post


@router.patch("/page/{id}", status_code=200, response_model=PostDetailSchema)#본문 수정
def update_post_handler(
    id: int,
    title: Optional[str] = Body(None, embed=True),
    contents: Optional[str] = Body(None, embed=True),
    session: Session = Depends(get_db),
):
    post = session.scalar(
        select(Post).where(Post.id == id).where(Post.is_deleted == False)
    )
    if post is None:
        raise HTTPException(status_code=404, detail="post not found")

    if title is not None:
        post.title = title
    if contents is not None:
        post.contents = contents
    post.updated_at = datetime.now(timezone.utc)
    session.commit()
    session.refresh(post)

    post.comments = [c for c in post.comments if not c.is_deleted]
    return post


@router.delete("/page/{id}", status_code=204)#본문 삭제
def delete_post_handler(
    id: int,
    session: Session = Depends(get_db),
):
    post = session.scalar(
        select(Post).where(Post.id == id).where(Post.is_deleted == False)
    )
    if post is None:
        raise HTTPException(status_code=404, detail="post not found")

    post.is_deleted = True
    post.updated_at = datetime.now(timezone.utc)
    session.commit()
    return