from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, JSON
from sqlalchemy.orm import relationship
from datetime import datetime, UTC
from ..database import Base


class Project(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    name = Column(String(200), nullable=False)

    # Контекст проекта (JSON)
    context_json = Column(JSON, nullable=True)  # {subject, grade, topic, original_plan_text, free_prompt}

    # Токен для публичного доступа (персональная ссылка)
    share_token = Column(String(100), unique=True, index=True, nullable=True)

    # Метаданные
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))
    updated_at = Column(DateTime, default=lambda: datetime.now(UTC),
                        onupdate=lambda: datetime.now(UTC))
    last_accessed_at = Column(DateTime, default=lambda: datetime.now(UTC),
                              onupdate=lambda: datetime.now(UTC))

    # Связи
    user = relationship("User", backref="projects")
    handouts = relationship("Handout", back_populates="project", cascade="all, delete-orphan")
    uploaded_files = relationship("UploadedFile", back_populates="project", cascade="all, delete-orphan")
