from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Enum as SQLEnum
from sqlalchemy.orm import relationship
from datetime import datetime, UTC
import enum
from ..database import Base


class HandoutType(str, enum.Enum):
    WORK_SHEET = "work_sheet"  # Рабочий лист
    MEMO = "memo"  # Памятка
    TABLE = "table"  # Таблица для заполнения
    SCHEME = "scheme"  # Схема с пропусками
    REFLECTION = "reflection"  # Бланк рефлексии
    CARDS = "cards"  # Карточки
    OTHER = "other"  # Другое


class HandoutStatus(str, enum.Enum):
    PENDING = "pending"  # Ожидает генерации
    GENERATING = "generating"  # В процессе генерации
    READY = "ready"  # Сгенерирован
    ERROR = "error"  # Ошибка при генерации


class Handout(Base):
    __tablename__ = "handouts"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False, index=True)

    # Привязка к этапу урока
    stage_order = Column(Integer, nullable=False)  # Порядковый номер этапа
    stage_name = Column(String(200), nullable=False)  # Название этапа (из плана или пользователь)
    stage_description = Column(Text, nullable=True)  # Описание этапа (цель, тип деятельности)

    # Данные раздатки
    handout_type = Column(SQLEnum(HandoutType, native_enum=False), nullable=False)
    content = Column(Text, nullable=True)  # HTML или Markdown контент
    status = Column(SQLEnum(HandoutStatus, native_enum=False), default=HandoutStatus.PENDING, nullable=False)

    # Метаданные
    error_message = Column(Text, nullable=True)  # Если status = ERROR
    generated_at = Column(DateTime, nullable=True)  # Когда сгенерирован
    version = Column(Integer, default=1, nullable=False)  # Текущая версия

    created_at = Column(DateTime, default=lambda: datetime.now(UTC))
    updated_at = Column(DateTime, default=lambda: datetime.now(UTC),
                        onupdate=lambda: datetime.now(UTC))

    # Связи
    project = relationship("Project", back_populates="handouts")
    versions = relationship("HandoutVersion", back_populates="handout", cascade="all, delete-orphan")