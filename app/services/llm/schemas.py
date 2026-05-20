from pydantic import BaseModel
from typing import List, Optional
from enum import Enum

class HandoutType(str, Enum):
    WORK_SHEET = "work_sheet"
    MEMO = "memo"
    TABLE = "table"
    SCHEME = "scheme"
    REFLECTION = "reflection"
    CARDS = "cards"

class Stage(BaseModel):
    name: str
    description: str

class PlanGenerationResult(BaseModel):
    stages: List[Stage]
    subject: str
    grade: str
    topic: str

class HandoutGenerationResult(BaseModel):
    content: str
    tokens_used: Optional[int] = None
