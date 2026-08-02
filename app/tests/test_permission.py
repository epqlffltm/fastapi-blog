#app/tests/test_permission.py

'''
2026-07-30
관리 엔드포인트가 AdminAuditRepository 로 옮겨져 목 대상 변경

2026-07-24
권한 체크박스 / 정지 · 강퇴 테스트
'''

from datetime import datetime, timedelta, timezone
from app.database.orm import User, PERMISSION_NAMES


def _make_user(id=2, nickname="other", **kwargs):
    defaults = dict(
        email=f"{nickname}@example.com", password="hash",
        nickname=nickname, is_verified=True,
        can_comment=True, can_write_post=False, can_upload=False,
        can_manage_category=False, can_manage_user=False,
        suspended_until=None, is_banned=False,
        created_at=datetime(2026, 7, 23, tzinfo=timezone.utc),
        can_manage_post=False,
    )
    defaults.update(kwargs)
    return User(id=id, **defaults)


# ---------- 회원 목록 ----------

def test_get_users(admin_client, mock_user_repo):
    mock_user_repo.get_users.return_value = [
        _make_user(id=1, nickname="boss", can_manage_user=True),
        _make_user(id=2, nickname="member"),
    ]

    response = admin_client.get("/user/list")

    assert response.status_code == 200
    users = response.json()["users"]
    assert len(users) == 2
    assert users[0]["can_manage_user"] is True
    assert users[1]["can_manage_user"] is False
    assert "password" not in users[0]      # 목록에도 비번이 새면 안 된다


def test_get_users_without_permission(auth_client, mock_user_repo):
    response = auth_client.get("/user/list")

    assert response.status_code == 403
    assert response.json()["detail"] == "permission denied: can_manage_user"


def test_get_users_without_token(client, mock_user_repo):
    response = client.get("/user/list")

    assert response.status_code == 401


# ---------- 권한 변경 ----------

def test_grant_permission(admin_client, mock_admin_audit_repo):
    target = _make_user(id=2)
    mock_admin_audit_repo.get_user_by_id_for_update.return_value = target
    mock_admin_audit_repo.save_user_change.return_value = target

    response = admin_client.patch("/user/2/permissions", json={"can_write_post": True})

    assert response.status_code == 200
    assert response.json()["can_write_post"] is True
    assert target.can_write_post is True


def test_revoke_permission(admin_client, mock_admin_audit_repo):
    target = _make_user(id=2, can_upload=True)
    mock_admin_audit_repo.get_user_by_id_for_update.return_value = target
    mock_admin_audit_repo.save_user_change.return_value = target

    response = admin_client.patch("/user/2/permissions", json={"can_upload": False})

    assert response.status_code == 200
    assert target.can_upload is False


def test_update_only_sent_permissions(admin_client, mock_admin_audit_repo):
    """보내지 않은 항목은 건드리지 않는다"""
    target = _make_user(id=2, can_comment=True, can_upload=True)
    mock_admin_audit_repo.get_user_by_id_for_update.return_value = target
    mock_admin_audit_repo.save_user_change.return_value = target

    admin_client.patch("/user/2/permissions", json={"can_write_post": True})

    assert target.can_comment is True      # 그대로
    assert target.can_upload is True       # 그대로
    assert target.can_write_post is True   # 바뀐 것


def test_cannot_change_own_permissions(admin_client, current_user, mock_admin_audit_repo):
    """자기 권한을 내리면 마지막 관리자가 사라질 수 있다"""
    response = admin_client.patch(
        f"/user/{current_user.id}/permissions", json={"can_manage_user": False}
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "cannot change your own permissions"
    mock_admin_audit_repo.save_user_change.assert_not_called()


def test_change_permission_without_permission(auth_client, mock_admin_audit_repo):
    response = auth_client.patch("/user/2/permissions", json={"can_write_post": True})

    assert response.status_code == 403
    mock_admin_audit_repo.save_user_change.assert_not_called()


def test_change_permission_user_not_found(admin_client, mock_admin_audit_repo):
    mock_admin_audit_repo.get_user_by_id_for_update.return_value = None

    response = admin_client.patch("/user/999/permissions", json={"can_write_post": True})

    assert response.status_code == 404


def test_change_permission_unknown_field(admin_client, mock_admin_audit_repo):
    """정의되지 않은 권한 이름은 무시된다 (스키마에 없는 키)"""
    target = _make_user(id=2)
    mock_admin_audit_repo.get_user_by_id_for_update.return_value = target
    mock_admin_audit_repo.save_user_change.return_value = target

    response = admin_client.patch("/user/2/permissions", json={"can_do_anything": True})

    assert response.status_code == 200
    assert not hasattr(target, "can_do_anything")


# ---------- 정지 ----------

def test_suspend_user(admin_client, mock_admin_audit_repo):
    target = _make_user(id=2)
    mock_admin_audit_repo.get_user_by_id_for_update.return_value = target
    mock_admin_audit_repo.save_user_change.return_value = target

    response = admin_client.patch("/user/2/suspend", json={"days": 7})

    assert response.status_code == 200
    assert response.json()["is_suspended"] is True
    assert target.suspended_until is not None
    assert target.is_suspended is True


def test_release_suspension(admin_client, mock_admin_audit_repo):
    """days=0 이면 해제"""
    target = _make_user(
        id=2, suspended_until=datetime.now(timezone.utc) + timedelta(days=3)
    )
    mock_admin_audit_repo.get_user_by_id_for_update.return_value = target
    mock_admin_audit_repo.save_user_change.return_value = target

    response = admin_client.patch("/user/2/suspend", json={"days": 0})

    assert response.status_code == 200
    assert target.suspended_until is None
    assert target.is_suspended is False


def test_cannot_suspend_self(admin_client, current_user, mock_admin_audit_repo):
    response = admin_client.patch(
        f"/user/{current_user.id}/suspend", json={"days": 7}
    )

    assert response.status_code == 400
    mock_admin_audit_repo.save_user_change.assert_not_called()


def test_suspend_without_permission(auth_client, mock_admin_audit_repo):
    response = auth_client.patch("/user/2/suspend", json={"days": 7})

    assert response.status_code == 403
    mock_admin_audit_repo.save_user_change.assert_not_called()


def test_suspend_invalid_days(admin_client, mock_admin_audit_repo):
    response = admin_client.patch("/user/2/suspend", json={"days": -1})

    assert response.status_code == 422
    mock_admin_audit_repo.save_user_change.assert_not_called()


def test_expired_suspension_is_not_active():
    """기한이 지난 정지는 저절로 풀린다"""
    user = _make_user(suspended_until=datetime.now(timezone.utc) - timedelta(days=1))

    assert user.is_suspended is False
    assert user.is_active is True


def test_suspended_until_in_future_is_suspended():
    """정지 해제 시각이 미래면 is_suspended True (컬럼이 timestamptz 라 aware 로 비교)"""
    future = datetime.now(timezone.utc) + timedelta(days=1)
    user = _make_user(suspended_until=future)

    assert user.is_suspended is True


def test_suspended_until_in_past_is_not_suspended():
    """정지 해제 시각이 지났으면 is_suspended False"""
    past = datetime.now(timezone.utc) - timedelta(days=1)
    user = _make_user(suspended_until=past)

    assert user.is_suspended is False


# ---------- 강퇴 ----------

def test_ban_user(admin_client, mock_admin_audit_repo):
    target = _make_user(id=2)
    mock_admin_audit_repo.get_user_by_id_for_update.return_value = target
    mock_admin_audit_repo.save_user_change.return_value = target

    response = admin_client.patch("/user/2/ban", json={"banned": True})

    assert response.status_code == 200
    assert response.json()["is_banned"] is True
    assert target.is_active is False


def test_unban_user(admin_client, mock_admin_audit_repo):
    target = _make_user(id=2, is_banned=True)
    mock_admin_audit_repo.get_user_by_id_for_update.return_value = target
    mock_admin_audit_repo.save_user_change.return_value = target

    response = admin_client.patch("/user/2/ban", json={"banned": False})

    assert response.status_code == 200
    assert target.is_banned is False


def test_cannot_ban_self(admin_client, current_user, mock_admin_audit_repo):
    response = admin_client.patch(f"/user/{current_user.id}/ban", json={"banned": True})

    assert response.status_code == 400
    mock_admin_audit_repo.save_user_change.assert_not_called()


def test_ban_without_permission(auth_client, mock_admin_audit_repo):
    response = auth_client.patch("/user/2/ban", json={"banned": True})

    assert response.status_code == 403
    mock_admin_audit_repo.save_user_change.assert_not_called()


# ---------- 제재된 계정의 행동 ----------

def test_suspended_cannot_comment(suspended_client, mock_post_repo, mock_comment_repo):
    response = suspended_client.post("/page/1/comment", json={"contents": "댓글"})

    assert response.status_code == 403
    assert response.json()["detail"] == "suspended"
    mock_comment_repo.save.assert_not_called()


def test_banned_cannot_comment(banned_client, mock_post_repo, mock_comment_repo):
    response = banned_client.post("/page/1/comment", json={"contents": "댓글"})

    assert response.status_code == 403
    assert response.json()["detail"] == "banned"
    mock_comment_repo.save.assert_not_called()


def test_suspended_cannot_write_post(suspended_client, mock_post_repo, mock_category_repo):
    response = suspended_client.post(
        "/page", json={"title": "글", "contents": "본문", "category_id": 1}
    )

    assert response.status_code == 403
    mock_post_repo.save.assert_not_called()


def test_suspended_can_read(suspended_client, mock_post_repo, mock_category_repo):
    """읽기는 제재와 무관하다"""
    mock_post_repo.get_posts.return_value = ([], 0)

    response = suspended_client.get("/pages")

    assert response.status_code == 200


def test_suspended_can_see_own_status(suspended_client, mock_user_repo):
    """왜 막혔는지 본인이 확인할 수 있어야 한다"""
    response = suspended_client.get("/user/me")

    assert response.status_code == 200
    assert response.json()["is_suspended"] is True


def test_banned_can_see_own_status(banned_client, mock_user_repo):
    response = banned_client.get("/user/me")

    assert response.status_code == 200
    assert response.json()["is_banned"] is True


# ---------- 가입 기본값 ----------

def test_sign_up_has_comment_only(client, mock_user_repo):
    mock_user_repo.get_user_by_email.return_value = None
    mock_user_repo.get_user_by_nickname.return_value = None
    mock_user_repo.save_user.return_value = _make_user(id=3, nickname="newbie")

    client.post(
        "/user/sign-up",
        json={"email": "new@example.com", "password": "password123", "nickname": "newbie"},
    )

    # 반환값이 아니라 save_user 에 넘어간 객체를 본다
    saved = mock_user_repo.save_user.call_args.args[0]
    assert saved.can_comment is True
    for name in PERMISSION_NAMES:
        if name != "can_comment":
            assert getattr(saved, name) is False


def test_grant_all_and_revoke_all():
    user = _make_user()

    user.grant_all()
    assert all(getattr(user, name) for name in PERMISSION_NAMES)

    user.revoke_all()
    assert not any(getattr(user, name) for name in PERMISSION_NAMES)