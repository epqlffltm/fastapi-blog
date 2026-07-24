#app/tests/test_category.py

'''
2026-07-24
분류 API 테스트
'''

from app.database.orm import Category


def _make_category(id=1, slug="dnd", name="TRPG", order=0):
    return Category(id=id, slug=slug, name=name, display_order=order)


def test_get_categories(client, mock_category_repo):
    mock_category_repo.get_categories_with_counts.return_value = [
        (_make_category(1, "dnd", "TRPG", 0), 3),
        (_make_category(2, "dev", "개발", 1), 0),
    ]

    response = client.get("/categories")

    assert response.status_code == 200
    data = response.json()["categories"]
    assert len(data) == 2
    assert data[0] == {"id": 1, "slug": "dnd", "name": "TRPG", "post_count": 3}
    assert data[1]["post_count"] == 0      # 글 없는 분류도 나와야 한다


def test_get_categories_empty(client, mock_category_repo):
    mock_category_repo.get_categories_with_counts.return_value = []

    response = client.get("/categories")

    assert response.status_code == 200
    assert response.json()["categories"] == []