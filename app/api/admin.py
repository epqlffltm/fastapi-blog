#app/api/admin.py

"""관리자 전용 조회 API."""

from fastapi import APIRouter, Depends, Query

from ..database.audit_repository import AdminAuditRepository
from ..database.orm import User
from ..schema.response import ListAdminAuditLogSchema
from .dependency import require_permission

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get(
    "/audit-logs",
    status_code=200,
    response_model=ListAdminAuditLogSchema,
)
async def get_admin_audit_logs_handler(
    page: int = Query(default=1, ge=1),
    size: int = Query(default=50, ge=1, le=100),
    action: str | None = Query(default=None, max_length=64),
    target_id: int | None = Query(default=None, ge=1),
    _current_user: User = Depends(require_permission("can_manage_user")),
    audit_repo: AdminAuditRepository = Depends(),
):
    logs, total = await audit_repo.get_logs(
        page=page,
        size=size,
        action=action,
        target_id=target_id,
    )
    total_pages = (total + size - 1) // size
    return ListAdminAuditLogSchema(
        logs=logs,
        page=page,
        size=size,
        total=total,
        total_pages=total_pages,
    )
