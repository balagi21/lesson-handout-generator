from datetime import datetime, UTC
from sqlalchemy import select, update
from ...models.user_quota import UserQuota


async def create_user_quota(db, user_id):
    """Создаёт запись в таблице user_quota. Не коммитит данные в БД"""
    new_quota = UserQuota(
        user_id=user_id,
        daily_requests=0,
        daily_limit=50,
        total_generated=0,
        last_reset_date=datetime.now(UTC)
    )
    db.add(new_quota)


async def get_user_quota(db, user_id):
    db_result = await db.execute(
        select(UserQuota).where(UserQuota.user_id == user_id)
    )
    quota = db_result.scalar_one_or_none()
    if quota:
        return {'daily_requests': quota.daily_requests, 'daily_limit': quota.daily_limit}
    return {'daily_requests': 0, 'daily_limit': 50}


async def consume_quota(db, user_id: int, amount: int = 1):
    """Израсходовать amount запросов в квоте пользователя"""
    result = await db.execute(
        update(UserQuota)
        .where(
            UserQuota.user_id == user_id,
            UserQuota.daily_requests + amount <= UserQuota.daily_limit
        )
        .values(
            daily_requests=UserQuota.daily_requests + amount,
            total_generated=UserQuota.total_generated + amount
        )
    )
    await db.commit()

    return result.rowcount > 0
