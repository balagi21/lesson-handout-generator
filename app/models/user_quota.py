from sqlalchemy import Column, Integer, DateTime, ForeignKey
from datetime import datetime, UTC
from ..database import Base


class UserQuota(Base):
    __tablename__ = "user_quotas"
    user_id = Column(Integer, ForeignKey("users.id"), primary_key=True, index=True)

    # Лимиты
    daily_requests = Column(Integer, default=0, nullable=False)  # Использовано сегодня
    daily_limit = Column(Integer, default=50, nullable=False)  # Лимит в день
    total_generated = Column(Integer, default=0, nullable=False)  # Всего за всё время

    last_reset_date = Column(DateTime, default=lambda: datetime.now(UTC))
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))
    updated_at = Column(DateTime, default=lambda: datetime.now(UTC),
                        onupdate=lambda: datetime.now(UTC))