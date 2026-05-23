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
    def generate_plan_from_prompt(
            self,
            prompt: str,
            subject: Optional[str] = None,
            grade: Optional[str] = None,
            topic: Optional[str] = None
    ) -> PlanGenerationResult:
        """Генерация плана урока из текстового описания"""
        pass

    @abstractmethod
    def generate_plan_from_text(
            self,
            text: str,
            filename: Optional[str] = None
    ) -> PlanGenerationResult:
        """Генерация плана урока из текста файла"""
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
    def extract_metadata(self, text: str) -> dict:
        """Извлечение предмета, класса, темы из текста"""
        pass
