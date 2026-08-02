"""관리자 작업과 감사 로그를 같은 DB 트랜잭션으로 저장한다."""

from fastapi import Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from .connection import get_db
from .orm import AdminAuditLog, User


class AdminAuditRepository:
    def __init__(self, session: AsyncSession = Depends(get_db)):
        self.session = session

    async def get_user_by_id_for_update(self, user_id: int) -> User | None:
        """동시에 두 관리자가 같은 사용자를 바꾸지 못하도록 행 잠금을 잡는다."""
        return await self.session.scalar(
            select(User)
            .where(User.id == user_id)
            .with_for_update()
        )

    async def save_user_change(
        self,
        user: User,
        audit_log: AdminAuditLog,
    ) -> User:
        """사용자 변경과 감사 로그 INSERT를 원자적으로 커밋한다."""
        try:
            self.session.add(audit_log)
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            raise

        await self.session.refresh(user)
        await self.session.refresh(audit_log)
        return user

    async def get_logs(
        self,
        *,
        page: int,
        size: int,
        action: str | None = None,
        target_id: int | None = None,
    ) -> tuple[list[AdminAuditLog], int]:
        filters = []
        if action is not None:
            filters.append(AdminAuditLog.action == action)
        if target_id is not None:
            filters.append(AdminAuditLog.target_id == target_id)

        total = await self.session.scalar(
            select(func.count(AdminAuditLog.id)).where(*filters)
        )

        rows = await self.session.scalars(
            select(AdminAuditLog)
            .where(*filters)
            .order_by(
                AdminAuditLog.created_at.desc(),
                AdminAuditLog.id.desc(),
            )
            .offset((page - 1) * size)
            .limit(size)
        )
        return list(rows.all()), int(total or 0)
