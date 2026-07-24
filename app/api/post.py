#app/api/post.py

'''
2026-07-21
글 관련 라우터 (목록, 상세, 생성, 수정, 삭제)
repository 패턴 적용

2026-07-23
인증 연동 + 권한 검사

2026-07-24
글 작성에 이메일 인증 요구
분류 필터 / 분류 검증
'''

from fastapi import APIRouter, Depends, HTTPException, Body
from datetime import datetime, timezone
from typing import Optional
from ..database.repository import PostRepository, CategoryRepository
from ..database.orm import Post, User
from ..schema.request import PostCreate
from ..schema.response import (
    ListPostSchema, PostListItemSchema, PostDetailSchema,
    UserBriefSchema, CategorySchema,
)
from .dependency import get_current_user, get_verified_user

router = APIRouter(tags=["post"])


@router.get("/pages", status_code=200, response_model=ListPostSchema)#글 목록 보기
def get_pages_handler(
    order: str = "random",
    category: str | None = None,
    post_repo: PostRepository = Depends(),
    category_repo: CategoryRepository = Depends(),
):
    category_id = None
    if category is not None:
        found = category_repo.get_category_by_slug(category)
        if found is None:
            raise HTTPException(status_code=404, detail="category not found")
        category_id = found.id

    posts = post_repo.get_posts(order=order.lower(), category_id=category_id)

    result = []
    for post in posts:
        comment_count = post_repo.count_comments(post.id)
        result.append(
            PostListItemSchema(
                id=post.id,
                title=post.title,
                user=UserBriefSchema.model_validate(post.user),
                category=CategorySchema.model_validate(post.category),
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

    # 삭제 안 된 댓글만 남기기 (relationship은 삭제 여부를 안 가리므로 직접 필터)
    post.comments = [c for c in post.comments if not c.is_deleted]
    return post


@router.post("/page", status_code=201, response_model=PostDetailSchema)#본문 쓰기
def create_post_handler(
    request: PostCreate,
    current_user: User = Depends(get_verified_user),   # 이메일 인증된 회원만
    post_repo: PostRepository = Depends(),
    category_repo: CategoryRepository = Depends(),
):
    if category_repo.get_category_by_id(request.category_id) is None:
        raise HTTPException(status_code=400, detail="category not found")

    post = Post.create(request=request, user_id=current_user.id)
    post = post_repo.save_with_images(post=post, image_urls=request.image)
    return post


@router.patch("/page/{id}", status_code=200, response_model=PostDetailSchema)#본문 수정
def update_post_handler(
    id: int,
    title: Optional[str] = Body(None, embed=True),
    contents: Optional[str] = Body(None, embed=True),
    current_user: User = Depends(get_current_user),
    post_repo: PostRepository = Depends(),
):
    post = post_repo.get_post_by_id(id)
    if post is None:
        raise HTTPException(status_code=404, detail="post not found")
    if post.user_id != current_user.id:      # 내 글만 수정 가능
        raise HTTPException(status_code=403, detail="not your post")

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
    current_user: User = Depends(get_current_user),
    post_repo: PostRepository = Depends(),
):
    post = post_repo.get_post_by_id(id)
    if post is None:
        raise HTTPException(status_code=404, detail="post not found")
    if post.user_id != current_user.id:      # 내 글만 삭제 가능
        raise HTTPException(status_code=403, detail="not your post")

    post.is_deleted = True
    post.updated_at = datetime.now(timezone.utc)
    post_repo.update(post)
    return