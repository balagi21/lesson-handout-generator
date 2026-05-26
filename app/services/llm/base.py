from abc import ABC, abstractmethod
from typing import Optional, ClassVar
from .schemas import PlanGenerationResult, HandoutGenerationResult, HandoutType


class BaseLLMProvider(ABC):
    """Абстрактный класс для всех LLM провайдеров"""

    # Название поля в settings, где лежит API ключ
    settings_key: ClassVar[str]

    def __init__(self, api_key: str):
        self.api_key = api_key

    @abstractmethod
    def generate_plan(
            self,
            prompt: str,
            file_content: str,
            subject: Optional[str] = None,
            grade: Optional[str] = None,
            topic: Optional[str] = None
    ) -> PlanGenerationResult:
        """Генерация плана урока из текстового описания"""
        pass

    @abstractmethod
    def generate_handout(
            self,
            subject: str,
            grade: str,
            topic: str,
            handout_type: HandoutType,
            description: str
    ) -> HandoutGenerationResult:
        """Генерация раздаточного материала для этапа"""
        pass

    @abstractmethod
    def extract_file_content(self, file_content: str):
        """По содержимому файла извлекает только релевантные для генерации данные"""
        pass
