from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models import AdminAuditLog


async def log_admin_action(
    session: AsyncSession,
    admin_telegram_id: int,
    action: str,
    target_type: str | None = None,
    target_id: int | None = None,
    details: str | None = None,
) -> None:
    session.add(
        AdminAuditLog(
            admin_telegram_id=admin_telegram_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            details=details,
        )
    )
    await session.commit()
