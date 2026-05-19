from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from datetime import datetime, UTC
from ..database import Base


class HandoutVersion(Base):
    __tablename__ = "handout_versions"

    id = Column(Integer, primary_key=True, index=True)
    handout_id = Column(Integer, ForeignKey("handouts.id"), nullable=False, index=True)
    version_number = Column(Integer, nullable=False)
    content = Column(Text, nullable=False)  # Снапшот контента на момент версии
    changed_by = Column(String(50), nullable=True)  # Кто изменил: "user" или "ai"
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))

    # Связи
    handout = relationship("Handout", back_populates="versions")