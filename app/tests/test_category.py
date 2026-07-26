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


def test_create_category_without_permission(auth_client, mock_category_repo):
    """사이드바 구성은 분류 관리 권한이 있어야 한다"""
    response = auth_client.post("/categories", json={"slug": "book", "name": "독서"})

    assert response.status_code == 403
    assert response.json()["detail"] == "permission denied: can_manage_category"
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
    
# ---------- 이름 변경 ----------

def test_update_category(admin_client, mock_category_repo):
    target = _make_category(id=1, slug="dnd", name="TRPG")
    mock_category_repo.get_category_by_id.return_value = target
    mock_category_repo.get_category_by_name.return_value = None
    mock_category_repo.update.return_value = target

    response = admin_client.patch("/categories/1", json={"name": "테이블토크"})

    assert response.status_code == 200
    assert target.name == "테이블토크"
    mock_category_repo.update.assert_called_once()


def test_update_category_same_name_ok(admin_client, mock_category_repo):
    """자기 이름 그대로 저장은 허용 (중복 검사에 자기 자신 예외)"""
    target = _make_category(id=1, slug="dnd", name="TRPG")
    mock_category_repo.get_category_by_id.return_value = target
    mock_category_repo.get_category_by_name.return_value = target
    mock_category_repo.update.return_value = target

    response = admin_client.patch("/categories/1", json={"name": "TRPG"})

    assert response.status_code == 200


def test_update_category_duplicate_name(admin_client, mock_category_repo):
    target = _make_category(id=1, slug="dnd", name="TRPG")
    other = _make_category(id=2, slug="dev", name="개발")
    mock_category_repo.get_category_by_id.return_value = target
    mock_category_repo.get_category_by_name.return_value = other

    response = admin_client.patch("/categories/1", json={"name": "개발"})

    assert response.status_code == 409
    mock_category_repo.update.assert_not_called()


def test_update_category_not_found(admin_client, mock_category_repo):
    mock_category_repo.get_category_by_id.return_value = None
    response = admin_client.patch("/categories/999", json={"name": "뭐든"})
    assert response.status_code == 404


def test_update_category_without_permission(auth_client, mock_category_repo):
    response = auth_client.patch("/categories/1", json={"name": "새이름"})
    assert response.status_code == 403
    mock_category_repo.update.assert_not_called()


# ---------- 삭제 (미분류로 재배치) ----------

def test_delete_category_reassigns(admin_client, mock_category_repo):
    """분류를 지우면 글은 미분류로 옮기고 분류를 삭제한다"""
    target = _make_category(id=1, slug="dnd", name="TRPG")
    fallback = _make_category(id=9, slug="uncategorized", name="미분류")
    mock_category_repo.get_category_by_id.return_value = target
    mock_category_repo.get_category_by_slug.return_value = fallback

    response = admin_client.delete("/categories/1")

    assert response.status_code == 204
    mock_category_repo.reassign_and_delete.assert_called_once_with(target, 9)


def test_cannot_delete_uncategorized(admin_client, mock_category_repo):
    """미분류 자체는 삭제 금지 (안전망)"""
    target = _make_category(id=9, slug="uncategorized", name="미분류")
    mock_category_repo.get_category_by_id.return_value = target

    response = admin_client.delete("/categories/9")

    assert response.status_code == 409
    assert response.json()["detail"] == "cannot delete the default category"
    mock_category_repo.reassign_and_delete.assert_not_called()


def test_delete_category_not_found(admin_client, mock_category_repo):
    mock_category_repo.get_category_by_id.return_value = None
    response = admin_client.delete("/categories/999")
    assert response.status_code == 404


def test_delete_category_without_permission(auth_client, mock_category_repo):
    response = auth_client.delete("/categories/1")
    assert response.status_code == 403
    mock_category_repo.reassign_and_delete.assert_not_called()
    
    
def test_categories_hide_uncategorized_for_anonymous(client, mock_category_repo):
    """비로그인/일반 유저에겐 미분류가 목록에서 빠진다"""
    mock_category_repo.get_categories_with_counts.return_value = [
        (_make_category(1, "dnd", "TRPG", 0), 3),
        (_make_category(9, "uncategorized", "미분류", 99), 0),
    ]

    response = client.get("/categories")

    slugs = [c["slug"] for c in response.json()["categories"]]
    assert "uncategorized" not in slugs
    assert "dnd" in slugs


def test_categories_show_uncategorized_for_admin(admin_viewer, mock_category_repo):
    """분류 관리 권한이 있으면 미분류도 보인다"""
    mock_category_repo.get_categories_with_counts.return_value = [
        (_make_category(1, "dnd", "TRPG", 0), 3),
        (_make_category(9, "uncategorized", "미분류", 99), 0),
    ]

    response = admin_viewer.get("/categories")

    slugs = [c["slug"] for c in response.json()["categories"]]
    assert "uncategorized" in slugs