#app/api/category.py

'''
2026-07-24
분류 라우터 (사이드바용 목록 / 생성)

2026-07-25
이름 변경 / 삭제(미분류로 재배치 후 삭제)
'''

from fastapi import APIRouter, Depends, HTTPException
from ..database.orm import Category, User
from ..database.repository import CategoryRepository
from ..schema.request import CategoryCreate, CategoryUpdate
from ..schema.response import CategoryListItemSchema, CategorySchema, ListCategorySchema
from .dependency import require_permission

router = APIRouter(tags=["category"])


@router.get("/categories", status_code=200, response_model=ListCategorySchema)#분류 목록
def get_categories_handler(
    category_repo: CategoryRepository = Depends(),
):
    rows = category_repo.get_categories_with_counts()

    return ListCategorySchema(
        categories=[
            CategoryListItemSchema(
                id=category.id,
                slug=category.slug,
                name=category.name,
                post_count=count,
            )
            for category, count in rows
        ]
    )


@router.post("/categories", status_code=201, response_model=CategorySchema)#분류 추가
def create_category_handler(
    request: CategoryCreate,
    current_user: User = Depends(require_permission("can_manage_category")),
    category_repo: CategoryRepository = Depends(),
):
    if category_repo.get_category_by_slug(request.slug) is not None:
        raise HTTPException(status_code=409, detail="slug already exists")
    if category_repo.get_category_by_name(request.name) is not None:
        raise HTTPException(status_code=409, detail="name already exists")

    return category_repo.save(Category.create(request))


# 미분류: 분류 삭제 시 글이 모이는 안전망. 이 분류 자체는 삭제할 수 없다
UNCATEGORIZED_SLUG = "uncategorized"


@router.patch("/categories/{id}", status_code=200, response_model=CategorySchema)#분류 이름 변경
def update_category_handler(
    id: int,
    request: CategoryUpdate,
    current_user: User = Depends(require_permission("can_manage_category")),
    category_repo: CategoryRepository = Depends(),
):
    category = category_repo.get_category_by_id(id)
    if category is None:
        raise HTTPException(status_code=404, detail="category not found")

    # 다른 분류가 이미 쓰는 이름이면 막는다 (자기 자신은 예외)
    existing = category_repo.get_category_by_name(request.name)
    if existing is not None and existing.id != id:
        raise HTTPException(status_code=409, detail="name already exists")

    category.name = request.name
    return category_repo.update(category)


@router.delete("/categories/{id}", status_code=204)#분류 삭제 (글은 미분류로 이동)
def delete_category_handler(
    id: int,
    current_user: User = Depends(require_permission("can_manage_category")),
    category_repo: CategoryRepository = Depends(),
):
    category = category_repo.get_category_by_id(id)
    if category is None:
        raise HTTPException(status_code=404, detail="category not found")

    # 미분류는 안전망이라 삭제 금지 (사라지면 재배치할 곳이 없다)
    if category.slug == UNCATEGORIZED_SLUG:
        raise HTTPException(status_code=409, detail="cannot delete the default category")

    fallback = category_repo.get_category_by_slug(UNCATEGORIZED_SLUG)
    if fallback is None:
        # 미분류가 없으면 재배치할 곳이 없다 (seed 누락). 500 대신 명확히 알린다
        raise HTTPException(status_code=500, detail="default category is missing")

    # 이 분류의 글을 미분류로 옮긴 뒤 빈 분류를 삭제한다 (한 트랜잭션)
    category_repo.reassign_and_delete(category, fallback.id)
    return