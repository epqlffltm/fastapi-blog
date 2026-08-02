from datetime import datetime, timezone

from app.database.orm import AdminAuditLog, User


def _make_user(user_id: int) -> User:
    return User(
        id=user_id,
        email=f"user{user_id}@example.com",
        password="hash",
        token_version=0,
        nickname=f"user{user_id}",
        bio=None,
        avatar_url=None,
        is_verified=True,
        can_comment=True,
        can_write_post=False,
        can_upload=False,
        can_manage_category=False,
        can_manage_user=False,
        can_manage_post=False,
        suspended_until=None,
        is_banned=False,
        created_at=datetime(2026, 7, 30, tzinfo=timezone.utc),
    )


def test_permission_update_writes_audit_log(
    admin_client,
    mock_admin_audit_repo,
):
    target = _make_user(2)
    mock_admin_audit_repo.get_user_by_id_for_update.return_value = target
    mock_admin_audit_repo.save_user_change.return_value = target

    response = admin_client.patch(
        "/user/2/permissions",
        json={"can_write_post": True},
    )

    assert response.status_code == 200
    user, audit_log = mock_admin_audit_repo.save_user_change.await_args.args
    assert user is target
    assert audit_log.action == "user.permissions.update"
    assert audit_log.actor_user_id == 1
    assert audit_log.target_id == 2
    assert audit_log.before_data == {"can_write_post": False}
    assert audit_log.after_data == {"can_write_post": True}


def test_suspend_writes_audit_log(
    admin_client,
    mock_admin_audit_repo,
):
    target = _make_user(2)
    mock_admin_audit_repo.get_user_by_id_for_update.return_value = target
    mock_admin_audit_repo.save_user_change.return_value = target

    response = admin_client.patch(
        "/user/2/suspend",
        json={"days": 7},
    )

    assert response.status_code == 200
    _, audit_log = mock_admin_audit_repo.save_user_change.await_args.args
    assert audit_log.action == "user.suspension.update"
    assert audit_log.before_data == {"suspended_until": None}
    assert audit_log.after_data["suspended_until"] is not None


def test_ban_writes_audit_log(
    admin_client,
    mock_admin_audit_repo,
):
    target = _make_user(2)
    mock_admin_audit_repo.get_user_by_id_for_update.return_value = target
    mock_admin_audit_repo.save_user_change.return_value = target

    response = admin_client.patch(
        "/user/2/ban",
        json={"banned": True},
    )

    assert response.status_code == 200
    _, audit_log = mock_admin_audit_repo.save_user_change.await_args.args
    assert audit_log.action == "user.ban.update"
    assert audit_log.before_data == {"is_banned": False}
    assert audit_log.after_data == {"is_banned": True}


def test_audit_log_list_requires_manage_user(
    auth_client,
    mock_admin_audit_repo,
):
    response = auth_client.get("/admin/audit-logs")

    assert response.status_code == 403
    mock_admin_audit_repo.get_logs.assert_not_called()


def test_admin_can_list_audit_logs(
    admin_client,
    mock_admin_audit_repo,
):
    log = AdminAuditLog(
        id=1,
        actor_user_id=1,
        action="user.ban.update",
        target_type="user",
        target_id=2,
        before_data={"is_banned": False},
        after_data={"is_banned": True},
        ip_address="127.0.0.1",
        created_at=datetime(2026, 7, 30, tzinfo=timezone.utc),
    )
    mock_admin_audit_repo.get_logs.return_value = ([log], 1)

    response = admin_client.get(
        "/admin/audit-logs?page=1&size=20&target_id=2"
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["logs"][0]["action"] == "user.ban.update"
    mock_admin_audit_repo.get_logs.assert_awaited_once_with(
        page=1,
        size=20,
        action=None,
        target_id=2,
    )
