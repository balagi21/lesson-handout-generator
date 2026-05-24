from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, LargeBinary, Text
from sqlalchemy.orm import relationship
from datetime import datetime, UTC
from ..database import Base


class UploadedFile(Base):
    __tablename__ = "uploaded_files"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False, index=True)

    original_filename = Column(String(255), nullable=False)
    file_size = Column(Integer, nullable=True)  # Размер в байтах
    mime_type = Column(String(100), nullable=True)

    # Хранение файла (для MVP - в БД)
    file_data = Column(LargeBinary, nullable=True)  # Бинарные данные файла

    # Если требуется OCR или распознавание
    extracted_text = Column(Text, nullable=True)  # Извлечённый текст (результат парсинга)
    processing_status = Column(String(50), default="pending")  # pending, processing, completed, failed
    processing_error = Column(Text, nullable=True)

    created_at = Column(DateTime, default=lambda: datetime.now(UTC))

    # Связи
    project = relationship("Project", back_populates="uploaded_files")
