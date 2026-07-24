#app/api/category.py

'''
2026-07-24
분류 라우터 (사이드바용 목록 / 생성)
'''

from fastapi import APIRouter, Depends, HTTPException
from ..database.orm import Category, User
from ..database.repository import CategoryRepository
from ..schema.request import CategoryCreate
from ..schema.response import CategoryListItemSchema, CategorySchema, ListCategorySchema
from .dependency import get_admin_user

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
    current_user: User = Depends(get_admin_user),   # 사이드바 구성은 관리자만
    category_repo: CategoryRepository = Depends(),
):
    if category_repo.get_category_by_slug(request.slug) is not None:
        raise HTTPException(status_code=409, detail="slug already exists")
    if category_repo.get_category_by_name(request.name) is not None:
        raise HTTPException(status_code=409, detail="name already exists")

    return category_repo.save(Category.create(request))