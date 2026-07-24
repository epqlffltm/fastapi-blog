#app/tests/test_category.py

'''
2026-07-24
분류 API 테스트
'''

from app.database.orm import Category


def _make_category(id=1, slug="dnd", name="TRPG", order=0):
    return Category(id=id, slug=slug, name=name, display_order=order)


# ---------- 목록 ----------

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


# ---------- 생성 ----------

def test_create_category(admin_client, mock_category_repo):
    mock_category_repo.get_category_by_slug.return_value = None
    mock_category_repo.get_category_by_name.return_value = None
    mock_category_repo.save.return_value = _make_category(id=4, slug="book", name="독서")

    response = admin_client.post(
        "/categories", json={"slug": "book", "name": "독서", "display_order": 3}
    )

    assert response.status_code == 201
    assert response.json()["slug"] == "book"
    mock_category_repo.save.assert_called_once()


def test_create_category_as_member(auth_client, mock_category_repo):
    """사이드바 구성은 관리자만"""
    response = auth_client.post("/categories", json={"slug": "book", "name": "독서"})

    assert response.status_code == 403
    assert response.json()["detail"] == "admin only"
    mock_category_repo.save.assert_not_called()


def test_create_category_without_token(client, mock_category_repo):
    response = client.post("/categories", json={"slug": "book", "name": "독서"})

    assert response.status_code == 401
    mock_category_repo.save.assert_not_called()


def test_create_category_duplicate_slug(admin_client, mock_category_repo):
    mock_category_repo.get_category_by_slug.return_value = _make_category()

    response = admin_client.post("/categories", json={"slug": "dnd", "name": "다른이름"})

    assert response.status_code == 409
    assert response.json()["detail"] == "slug already exists"
    mock_category_repo.save.assert_not_called()


def test_create_category_duplicate_name(admin_client, mock_category_repo):
    mock_category_repo.get_category_by_slug.return_value = None
    mock_category_repo.get_category_by_name.return_value = _make_category()

    response = admin_client.post("/categories", json={"slug": "other", "name": "TRPG"})

    assert response.status_code == 409
    mock_category_repo.save.assert_not_called()


def test_create_category_invalid_slug(admin_client, mock_category_repo):
    """slug 는 URL 에 들어가므로 영소문자·숫자·하이픈만"""
    for bad in ["한글", "With Space", "UPPER", "sym!bol"]:
        response = admin_client.post("/categories", json={"slug": bad, "name": "이름"})
        assert response.status_code == 422, bad

    mock_category_repo.save.assert_not_called()