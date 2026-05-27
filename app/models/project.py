import enum
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, JSON, Enum as SQLEnum
from sqlalchemy.orm import relationship
from datetime import datetime, UTC
from ..database import Base


class ProjectStatus(str, enum.Enum):
    PLAN_GENERATION = "plan_generation"  # Шаг 1: Генерация плана урока
    HANDOUT_GENERATION = "handout_generation"  # Шаг 2: Генерация раздаточных материалов
    EDITING = "editing"  # Шаг 3: Редактирование итогового файла
    COMPLETED = "completed"


class Project(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    name = Column(String(200), nullable=False)

    status = Column(SQLEnum(ProjectStatus, native_enum=False), default=ProjectStatus.PLAN_GENERATION, nullable=False)

    context_json = Column(JSON, nullable=True)  # {subject, grade, topic, original_plan_text, free_prompt}
    compiled_content = Column(Text, nullable=True)

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
