#app/api/category.py

'''
2026-07-24
분류 라우터 (사이드바용 목록 / 생성)

2026-07-25
이름 변경 / 삭제(미분류로 재배치 후 삭제)

2026-07-26
미분류는 분류 관리 권한자에게만 목록에 노출
'''

from fastapi import APIRouter, Depends, HTTPException
from ..database.orm import Category, User
from ..database.repository import CategoryRepository
from ..schema.request import CategoryCreate, CategoryUpdate
from ..schema.response import CategoryListItemSchema, CategorySchema, ListCategorySchema
from .dependency import require_permission, get_current_user_optional

router = APIRouter(tags=["category"])

# 미분류: 분류 삭제 시 글이 모이는 안전망. 이 분류 자체는 삭제할 수 없고,
# 사이드바에는 분류 관리 권한자에게만 보인다
UNCATEGORIZED_SLUG = "uncategorized"


@router.get("/categories", status_code=200, response_model=ListCategorySchema)#분류 목록
async def get_categories_handler(
    viewer: User | None = Depends(get_current_user_optional),
    category_repo: CategoryRepository = Depends(),
):
    rows = await category_repo.get_categories_with_counts()

    # 미분류는 관리 화면 청소용이라, 분류 관리 권한이 있는 사람에게만 사이드바에 보인다
    can_see_uncategorized = viewer is not None and viewer.can_manage_category

    return ListCategorySchema(
        categories=[
            CategoryListItemSchema(
                id=category.id,
                slug=category.slug,
                name=category.name,
                post_count=count,
            )
            for category, count in rows
            if can_see_uncategorized or category.slug != UNCATEGORIZED_SLUG
        ]
    )


@router.post("/categories", status_code=201, response_model=CategorySchema)#분류 추가
async def create_category_handler(
    request: CategoryCreate,
    current_user: User = Depends(require_permission("can_manage_category")),
    category_repo: CategoryRepository = Depends(),
):
    if await category_repo.get_category_by_slug(request.slug) is not None:
        raise HTTPException(status_code=409, detail="slug already exists")
    if await category_repo.get_category_by_name(request.name) is not None:
        raise HTTPException(status_code=409, detail="name already exists")

    return await category_repo.save(Category.create(request))


@router.patch("/categories/{id}", status_code=200, response_model=CategorySchema)#분류 이름 변경
async def update_category_handler(
    id: int,
    request: CategoryUpdate,
    current_user: User = Depends(require_permission("can_manage_category")),
    category_repo: CategoryRepository = Depends(),
):
    category = await category_repo.get_category_by_id(id)
    if category is None:
        raise HTTPException(status_code=404, detail="category not found")

    # 다른 분류가 이미 쓰는 이름이면 막는다 (자기 자신은 예외)
    existing = await category_repo.get_category_by_name(request.name)
    if existing is not None and existing.id != id:
        raise HTTPException(status_code=409, detail="name already exists")

    category.name = request.name
    return await category_repo.update(category)


@router.delete("/categories/{id}", status_code=204)#분류 삭제 (글은 미분류로 이동)
async def delete_category_handler(
    id: int,
    current_user: User = Depends(require_permission("can_manage_category")),
    category_repo: CategoryRepository = Depends(),
):
    category = await category_repo.get_category_by_id(id)
    if category is None:
        raise HTTPException(status_code=404, detail="category not found")

    # 미분류는 안전망이라 삭제 금지 (사라지면 재배치할 곳이 없다)
    if category.slug == UNCATEGORIZED_SLUG:
        raise HTTPException(status_code=409, detail="cannot delete the default category")

    fallback = await category_repo.get_category_by_slug(UNCATEGORIZED_SLUG)
    if fallback is None:
        # 미분류가 없으면 재배치할 곳이 없다 (seed 누락). 500 대신 명확히 알린다
        raise HTTPException(status_code=500, detail="default category is missing")

    # 이 분류의 글을 미분류로 옮긴 뒤 빈 분류를 삭제한다 (한 트랜잭션)
    await category_repo.reassign_and_delete(category, fallback.id)
    return