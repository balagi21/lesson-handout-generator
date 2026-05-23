from sqlalchemy import Column, Integer, String, DateTime, Text, JSON
from datetime import datetime, UTC
from ..database import Base


class GenerationLog(Base):
    __tablename__ = "generation_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False, index=True)
    project_id = Column(Integer, nullable=True, index=True)
    handout_id = Column(Integer, nullable=True)

    # Детали запроса
    request_type = Column(String(50), nullable=False)  # stage_split, handout_generate, free_generate
    prompt = Column(Text, nullable=True)
    response = Column(Text, nullable=True)

    # Статус
    success = Column(Integer, default=0)  # 0 - false, 1 - true
    error_message = Column(Text, nullable=True)

    # Метрики
    tokens_used = Column(Integer, nullable=True)
    response_time_ms = Column(Integer, nullable=True)  # Время ответа в миллисекундах

    # Дополнительно
    metadata_json = Column(JSON, nullable=True)  # Любые дополнительные данные

    created_at = Column(DateTime, default=lambda: datetime.now(UTC))
