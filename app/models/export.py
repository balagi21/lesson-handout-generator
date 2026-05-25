from sqlalchemy import Column, Integer, ForeignKey, LargeBinary, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime, UTC
from ..database import Base


class ExportedPDF(Base):
    __tablename__ = "exported_pdfs"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False, unique=True, index=True)
    pdf_data = Column(LargeBinary, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC))
    updated_at = Column(DateTime, default=lambda: datetime.now(UTC),
                        onupdate=lambda: datetime.now(UTC))

    project = relationship("Project", backref="exported_pdf")

