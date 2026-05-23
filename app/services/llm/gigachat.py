import json
from typing import Optional
from pathlib import Path
from gigachat import GigaChat
from gigachat.models import Chat, Messages, MessagesRole
from .base import BaseLLMProvider
from .schemas import PlanGenerationResult, HandoutGenerationResult, HandoutType
from .prompts import SYSTEM_PROMPT_PLAN_FROM_PROMPT, SYSTEM_PROMPT_CREATE_HANDOUT, \
                     USER_PROMPT_CREATE_HANDOUT_TEMPLATE


class GigaChatProvider(BaseLLMProvider):
    """Взаимодействие с GigaChat"""

    def __init__(self, api_key: str):
        super().__init__(api_key)
        self._client = GigaChat(
            credentials=api_key,
            verify_ssl_certs=True,
            ca_bundle_file=str(Path(__file__).parent.parent.parent / "certs" / "russian_trusted_root_ca_pem.crt")
        )

    def generate_plan_from_prompt(
            self,
            prompt: str,
            subject: Optional[str] = None,
            grade: Optional[str] = None,
            topic: Optional[str] = None
    ) -> PlanGenerationResult:
        response = self._client.chat(Chat(messages=[
            Messages(role=MessagesRole.SYSTEM, content=SYSTEM_PROMPT_PLAN_FROM_PROMPT),
            Messages(role=MessagesRole.USER, content=prompt)
        ]))
        data = json.loads(response.choices[0].message.content)
        if data.get("error"):
            raise ValueError(data["message"])
        return PlanGenerationResult(
            subject=data["subject"],
            grade=data["grade"],
            topic=data["topic"],
            stages=data["stages"]
        )

    def generate_plan_from_text(
            self,
            text: str,
            filename: Optional[str] = None
    ) -> PlanGenerationResult:
        # TODO: реальный вызов GigaChat API
        return self.generate_plan_from_prompt(text[:200])

    def generate_handout(
            self,
            subject: str,
            grade: str,
            topic: str,
            handout_type: HandoutType,
            description: str
    ) -> HandoutGenerationResult:
        response = self._client.chat(Chat(messages=[
            Messages(role=MessagesRole.SYSTEM, content=SYSTEM_PROMPT_CREATE_HANDOUT),
            Messages(role=MessagesRole.USER, content=USER_PROMPT_CREATE_HANDOUT_TEMPLATE.format(
                subject=subject,
                grade=grade,
                topic=topic,
                handout_type=handout_type,
                description=description
            ))
        ]))
        content = response.choices[0].message.content
        return HandoutGenerationResult(content=content)

    async def extract_metadata(self, text: str) -> dict:
        # TODO: реальный вызов
        return {"subject": "Математика", "grade": "5", "topic": "Дроби"}
