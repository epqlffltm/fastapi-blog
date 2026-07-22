#app/api/post.py

'''
2026-07-21
글 관련 라우터 (목록, 상세, 생성, 수정, 삭제)
repository 패턴 적용
'''

from fastapi import APIRouter, Depends, HTTPException, Body
from datetime import datetime, timezone
from typing import Optional
from ..database.repository import PostRepository
from ..database.orm import Post
from ..schema.request import PostCreate
from ..schema.response import ListPostSchema, PostListItemSchema, PostDetailSchema

router = APIRouter(tags=["post"])


@router.get("/pages", status_code=200, response_model=ListPostSchema)#글 목록 보기
def get_pages_handler(
    order: str = "random",
    post_repo: PostRepository = Depends(),
):
    posts = post_repo.get_posts(order=order.lower())

    result = []
    for post in posts:
        comment_count = post_repo.count_comments(post.id)
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
    post_repo: PostRepository = Depends(),
):
    post = post_repo.get_post_by_id(id)
    if post is None:
        raise HTTPException(status_code=404, detail="post not found")

    post.comments = [c for c in post.comments if not c.is_deleted]
    return post


@router.post("/page", status_code=201, response_model=PostDetailSchema)#본문 쓰기
def create_post_handler(
    request: PostCreate,
    post_repo: PostRepository = Depends(),
):
    post = Post.create(request=request)
    post = post_repo.save_with_images(post=post, image_urls=request.image)
    return post


@router.patch("/page/{id}", status_code=200, response_model=PostDetailSchema)#본문 수정
def update_post_handler(
    id: int,
    title: Optional[str] = Body(None, embed=True),
    contents: Optional[str] = Body(None, embed=True),
    post_repo: PostRepository = Depends(),
):
    post = post_repo.get_post_by_id(id)
    if post is None:
        raise HTTPException(status_code=404, detail="post not found")

    if title is not None:
        post.title = title
    if contents is not None:
        post.contents = contents
    post.updated_at = datetime.now(timezone.utc)
    post = post_repo.update(post)

    post.comments = [c for c in post.comments if not c.is_deleted]
    return post


@router.delete("/page/{id}", status_code=204)#본문 삭제
def delete_post_handler(
    id: int,
    post_repo: PostRepository = Depends(),
):
    post = post_repo.get_post_by_id(id)
    if post is None:
        raise HTTPException(status_code=404, detail="post not found")

    post.is_deleted = True
    post.updated_at = datetime.now(timezone.utc)
    post_repo.update(post)
    return