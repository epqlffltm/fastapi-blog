#app/api/post.py

'''
2026-07-21
글 관련 라우터 (목록, 상세, 생성, 수정, 삭제)
repository 패턴 적용

2026-07-23
인증 연동 + 권한 검사

2026-07-24
분류 필터 / 분류 검증
본문 마크다운화 + 썸네일 추출
대댓글 표시 규칙 적용
권한 체크박스 연동

2026-07-25
관리자(can_manage_post) 남의 글 수정·삭제
삭제 글은 관리자에게만 목록·상세에 노출 (옵셔널 인증)
삭제 복구
글 분류 이동 (관리자, 미분류 청소)

2026-07-26
조회수 (IP별 Redis 중복 방지, 삭제 글 제외)
좋아요 토글 (likes 테이블, 매번 COUNT)

2026-07-28
게시글 수정 요청 스키마 검증
게시글 목록 페이지네이션 / 제목·본문·작성자 검색 / N+1 제거
Redis 장애 시 조회수만 포기하고 글 조회는 계속하도록 변경
신뢰 프록시 설정을 거친 실제 클라이언트 IP 사용
'''

import logging
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from datetime import datetime, timezone
from typing import Literal
from ..database.repository import PostRepository, CategoryRepository, LikeRepository
from ..database.orm import Post, User
from ..schema.request import PostCreate, PostUpdate, PostCategoryUpdate
from ..schema.response import (
    ListPostSchema, PostListItemSchema, PostDetailSchema,
    UserBriefSchema, CategorySchema, LikeResultSchema,
)
from ..service.client_ip import get_client_ip
from ..service.comment import visible_comments
from ..service.markdown import extract_first_image
from .dependency import (
    get_current_user, get_active_user, require_permission,
    get_current_user_optional,
)
from ..database.cache import get_redis_client
from redis.asyncio import Redis

router = APIRouter(tags=["post"])
logger = logging.getLogger(__name__)

# 같은 IP 의 재조회를 이 시간 동안은 세지 않는다 (새로고침 뻥튀기 방지)
VIEW_DEDUP_TTL_SECONDS = 60 * 60 * 6   # 6시간


@router.get("/pages", status_code=200, response_model=ListPostSchema)#글 목록 보기
async def get_pages_handler(
    order: Literal["asc", "desc", "random"] = "desc",
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
    q: str | None = Query(default=None, max_length=100),
    category: str | None = None,
    author: int | None = None,          # 특정 작성자의 글만 (프로필용)
    # 비로그인도 허용. 관리자면 삭제 글까지 본다
    viewer: User | None = Depends(get_current_user_optional),
    post_repo: PostRepository = Depends(),
    category_repo: CategoryRepository = Depends(),
):
    category_id = None
    if category is not None:
        found = await category_repo.get_category_by_slug(category)
        if found is None:
            raise HTTPException(status_code=404, detail="category not found")
        category_id = found.id

    # 빈 검색어는 검색하지 않은 것과 같게 처리한다.
    query = q.strip() if q and q.strip() else None

    # 관리자(글 관리 권한)만 삭제된 글도 목록에서 본다
    include_deleted = viewer is not None and viewer.can_manage_post
    rows, total = await post_repo.get_posts(
        order=order,
        page=page,
        size=size,
        query=query,
        category_id=category_id,
        user_id=author,
        include_deleted=include_deleted,
    )

    result = [
        PostListItemSchema(
            id=post.id,
            title=post.title,
            user=UserBriefSchema.model_validate(post.user),
            category=CategorySchema.model_validate(post.category),
            thumbnail_url=post.thumbnail_url,
            created_at=post.created_at,
            comment_count=comment_count,
            is_deleted=post.is_deleted,
            view_count=post.view_count,
            like_count=like_count,
        )
        for post, comment_count, like_count in rows
    ]

    total_pages = (total + size - 1) // size
    return ListPostSchema(
        posts=result,
        page=page,
        size=size,
        total=total,
        total_pages=total_pages,
    )


@router.get("/page/{id}", status_code=200, response_model=PostDetailSchema)#글 읽기
async def get_page_handler(
    id: int,
    request: Request,
    # 관리자면 삭제된 글도 열 수 있다. 아니면 안 잡혀서 404
    viewer: User | None = Depends(get_current_user_optional),
    post_repo: PostRepository = Depends(),
    redis: Redis = Depends(get_redis_client),
):
    is_admin = viewer is not None and viewer.can_manage_post
    post = await post_repo.get_post_by_id(id, include_deleted=is_admin)
    if post is None:
        raise HTTPException(status_code=404, detail="post not found")

    # 조회수: 삭제된 글(관리자만 봄)은 세지 않는다.
    # Redis 장애가 글 조회까지 막아서는 안 되므로 조회수만 포기한다.
    if not post.is_deleted:
        ip = get_client_ip(request)
        try:
            first_view = await redis.set(
                f"viewed:{post.id}:{ip}", "1", nx=True, ex=VIEW_DEDUP_TTL_SECONDS
            )
        except Exception:
            logger.exception(
                "view deduplication failed; serving post without increment",
                extra={"post_id": post.id},
            )
        else:
            if first_view:
                post.view_count = await post_repo.increment_view_count(post.id)

    # relationship 은 삭제 여부를 안 가리므로 표시 규칙을 직접 적용한다
    post.comments = visible_comments(post.comments)
    return post


@router.post("/page", status_code=201, response_model=PostDetailSchema)#본문 쓰기
async def create_post_handler(
    request: PostCreate,
    current_user: User = Depends(require_permission("can_write_post")),
    post_repo: PostRepository = Depends(),
    category_repo: CategoryRepository = Depends(),
):
    if await category_repo.get_category_by_id(request.category_id) is None:
        raise HTTPException(status_code=400, detail="category not found")

    post = Post.create(request=request, user_id=current_user.id)
    # 목록 미리보기용. 매번 본문을 훑지 않도록 쓸 때 한 번만 계산한다
    post.thumbnail_url = extract_first_image(request.contents)
    post = await post_repo.save(post)
    return post


@router.patch("/page/{id}", status_code=200, response_model=PostDetailSchema)#본문 수정
async def update_post_handler(
    id: int,
    request: PostUpdate,
    # 수정은 새 내용을 만드는 일이므로 제재 중엔 막는다.
    # 권한이 꺼져도 이미 쓴 글은 고칠 수 있게 소유권만 본다
    current_user: User = Depends(get_active_user),
    post_repo: PostRepository = Depends(),
):
    post = await post_repo.get_post_by_id(id)
    if post is None:
        raise HTTPException(status_code=404, detail="post not found")
    # 관리자(can_manage_post)는 남의 글도 손댈 수 있다. 아니면 작성자 본인만
    if post.user_id != current_user.id and not current_user.can_manage_post:
        raise HTTPException(status_code=403, detail="not your post")

    if request.title is not None:
        post.title = request.title
    if request.contents is not None:
        post.contents = request.contents
        # 본문이 바뀌면 썸네일도 다시 계산한다.
        post.thumbnail_url = extract_first_image(request.contents)
    post.updated_at = datetime.now(timezone.utc)
    post = await post_repo.update(post)

    post.comments = visible_comments(post.comments)
    return post


@router.delete("/page/{id}", status_code=204)#본문 삭제
async def delete_post_handler(
    id: int,
    # 지우는 건 언제나 허용한다. 제재 중이라고 자기 글을 못 내리게 할 이유가 없다
    current_user: User = Depends(get_current_user),
    post_repo: PostRepository = Depends(),
):
    post = await post_repo.get_post_by_id(id)
    if post is None:
        raise HTTPException(status_code=404, detail="post not found")
    # 관리자(can_manage_post)는 남의 글도 손댈 수 있다. 아니면 작성자 본인만
    if post.user_id != current_user.id and not current_user.can_manage_post:
        raise HTTPException(status_code=403, detail="not your post")

    post.is_deleted = True
    post.updated_at = datetime.now(timezone.utc)
    await post_repo.update(post)
    return

@router.post("/page/{id}/restore", status_code=200, response_model=PostDetailSchema)#삭제 복구
async def restore_post_handler(
    id: int,
    current_user: User = Depends(require_permission("can_manage_post")),
    post_repo: PostRepository = Depends(),
):
    # 삭제된 글이 대상이므로 include_deleted 로 찾는다
    post = await post_repo.get_post_by_id(id, include_deleted=True)
    if post is None:
        raise HTTPException(status_code=404, detail="post not found")

    post.is_deleted = False
    post.updated_at = datetime.now(timezone.utc)
    post = await post_repo.update(post)

    post.comments = visible_comments(post.comments)
    return post


@router.patch("/page/{id}/category", status_code=200, response_model=PostDetailSchema)#분류 이동
async def move_post_category_handler(
    id: int,
    request: PostCategoryUpdate,
    current_user: User = Depends(require_permission("can_manage_post")),
    post_repo: PostRepository = Depends(),
    category_repo: CategoryRepository = Depends(),
):
    # 삭제된 글도 옮길 수 있게 include_deleted 로 찾는다
    post = await post_repo.get_post_by_id(id, include_deleted=True)
    if post is None:
        raise HTTPException(status_code=404, detail="post not found")

    if await category_repo.get_category_by_id(request.category_id) is None:
        raise HTTPException(status_code=400, detail="category not found")

    post.category_id = request.category_id
    post.updated_at = datetime.now(timezone.utc)
    post = await post_repo.update(post)

    post.comments = visible_comments(post.comments)
    return post


@router.get("/page/{id}/like", status_code=200, response_model=LikeResultSchema)#좋아요 상태
async def get_like_handler(
    id: int,
    viewer: User | None = Depends(get_current_user_optional),
    post_repo: PostRepository = Depends(),
    like_repo: LikeRepository = Depends(),
):
    if await post_repo.get_post_by_id(id) is None:
        raise HTTPException(status_code=404, detail="post not found")

    # 비로그인은 누른 적이 없으니 liked=False
    liked = viewer is not None and await like_repo.exists(viewer.id, id)
    return LikeResultSchema(like_count=await like_repo.count_for_post(id), liked=liked)


@router.post("/page/{id}/like", status_code=200, response_model=LikeResultSchema)#좋아요 토글
async def toggle_like_handler(
    id: int,
    current_user: User = Depends(get_active_user),
    post_repo: PostRepository = Depends(),
    like_repo: LikeRepository = Depends(),
):
    # 삭제된 글은 get_post_by_id 가 안 잡아서 404 (삭제 글엔 좋아요 못 누른다)
    if await post_repo.get_post_by_id(id) is None:
        raise HTTPException(status_code=404, detail="post not found")

    # 이미 눌렀으면 취소, 아니면 좋아요 (버튼 한 번 더 = 취소)
    if await like_repo.exists(current_user.id, id):
        await like_repo.remove(current_user.id, id)
        liked = False
    else:
        await like_repo.add(current_user.id, id)
        liked = True

    return LikeResultSchema(like_count=await like_repo.count_for_post(id), liked=liked)
