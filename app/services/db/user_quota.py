from sqlalchemy import select
from ...models.user_quota import UserQuota


async def get_user_quota(db, user_id):
    db_result = await db.execute(
        select(UserQuota).where(UserQuota.user_id == user_id)
    )
    quota = db_result.scalar_one_or_none()
    if quota:
        return {'daily_requests': quota.daily_requests, 'daily_limit': quota.daily_limit}
    return {'daily_requests': 0, 'daily_limit': 50}
