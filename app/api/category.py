#app/api/category.py

'''
2026-07-24
분류 라우터 (사이드바용 목록)
'''

from fastapi import APIRouter, Depends
from ..database.repository import CategoryRepository
from ..schema.response import CategoryListItemSchema, ListCategorySchema

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