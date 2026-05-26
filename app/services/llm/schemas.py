from pydantic import BaseModel
from typing import List


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
