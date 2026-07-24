#app/tests/test_role.py

'''
2026-07-24
회원 등급 테스트
'''

from datetime import datetime, timezone
from app.database.orm import User, UserRole


def _make_user(id=2, nickname="other", role=UserRole.MEMBER):
    return User(
        id=id, email=f"{nickname}@example.com", password="hash",
        nickname=nickname, is_verified=True, role=role,
        created_at=datetime(2026, 7, 23, tzinfo=timezone.utc),
    )


# ---------- 회원 목록 ----------

def test_get_users(admin_client, mock_user_repo):
    mock_user_repo.get_users.return_value = [
        _make_user(id=1, nickname="admin", role=UserRole.ADMIN),
        _make_user(id=2, nickname="member"),
    ]

    response = admin_client.get("/user/list")

    assert response.status_code == 200
    users = response.json()["users"]
    assert len(users) == 2
    assert users[0]["role"] == "admin"
    assert "password" not in users[0]      # 목록에도 비번이 새면 안 된다


def test_get_users_as_member(auth_client, mock_user_repo):
    response = auth_client.get("/user/list")

    assert response.status_code == 403
    assert response.json()["detail"] == "admin only"


def test_get_users_without_token(client, mock_user_repo):
    response = client.get("/user/list")

    assert response.status_code == 401


# ---------- 등급 변경 ----------

def test_promote_user(admin_client, mock_user_repo):
    target = _make_user(id=2)
    mock_user_repo.get_user_by_id.return_value = target
    mock_user_repo.update_user.return_value = target

    response = admin_client.patch("/user/2/role", json={"role": "admin"})

    assert response.status_code == 200
    assert response.json()["role"] == "admin"
    assert target.role == UserRole.ADMIN


def test_demote_user(admin_client, mock_user_repo):
    target = _make_user(id=2, role=UserRole.ADMIN)
    mock_user_repo.get_user_by_id.return_value = target
    mock_user_repo.update_user.return_value = target

    response = admin_client.patch("/user/2/role", json={"role": "member"})

    assert response.status_code == 200
    assert target.role == UserRole.MEMBER


def test_cannot_change_own_role(admin_client, current_user, mock_user_repo):
    """자기 강등을 막지 않으면 마지막 관리자가 사라질 수 있다"""
    response = admin_client.patch(
        f"/user/{current_user.id}/role", json={"role": "member"}
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "cannot change your own role"
    mock_user_repo.update_user.assert_not_called()


def test_change_role_as_member(auth_client, mock_user_repo):
    response = auth_client.patch("/user/2/role", json={"role": "admin"})

    assert response.status_code == 403
    mock_user_repo.update_user.assert_not_called()


def test_change_role_user_not_found(admin_client, mock_user_repo):
    mock_user_repo.get_user_by_id.return_value = None

    response = admin_client.patch("/user/999/role", json={"role": "admin"})

    assert response.status_code == 404


def test_change_role_invalid_value(admin_client, mock_user_repo):
    """정해진 등급 외의 값은 스키마에서 걸린다"""
    response = admin_client.patch("/user/2/role", json={"role": "superuser"})

    assert response.status_code == 422
    mock_user_repo.update_user.assert_not_called()


# ---------- 가입은 항상 최하위 ----------

def test_sign_up_is_always_member(client, mock_user_repo):
    mock_user_repo.get_user_by_email.return_value = None
    mock_user_repo.get_user_by_nickname.return_value = None
    mock_user_repo.save_user.return_value = _make_user(id=3, nickname="newbie")

    client.post(
        "/user/sign-up",
        json={"email": "new@example.com", "password": "password123", "nickname": "newbie"},
    )

    # 반환값이 아니라 save_user 에 넘어간 객체를 본다
    saved = mock_user_repo.save_user.call_args.args[0]
    assert saved.role == UserRole.MEMBER