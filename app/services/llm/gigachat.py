import json
from typing import Optional
from pathlib import Path

from gigachat import GigaChat
from gigachat.models import Chat, Messages, MessagesRole
from .base import BaseLLMProvider
from .schemas import PlanGenerationResult, HandoutGenerationResult
from .prompts import SYSTEM_PROMPT_CREATE_PLAN, SYSTEM_PROMPT_CREATE_HANDOUT, \
                     USER_PROMPT_CREATE_HANDOUT_TEMPLATE, \
                     SYSTEM_PROMPT_EXTRACT_CONTENT


class GigaChatProvider(BaseLLMProvider):
    """Взаимодействие с GigaChat"""

    def __init__(self, api_key: str):
        super().__init__(api_key)
        self._client = GigaChat(
            credentials=api_key,
            verify_ssl_certs=True,
            # model="GigaChat-2-Pro",
            ca_bundle_file=str(Path(__file__).parent.parent.parent / "certs" / "russian_trusted_root_ca_pem.crt")
        )

    def generate_plan(
            self,
            prompt: str,
            file_content: str,
            subject: Optional[str] = None,
            grade: Optional[str] = None,
            topic: Optional[str] = None
    ) -> PlanGenerationResult:
        parsed_file_content = self.extract_file_content(file_content)
        prompt_text = ["Сгенерируй список этапов урока, для которых потребуются раздаточные материалы.\n\n"]
        if prompt:
            prompt_text.append(f"Пользовательский запрос: {prompt}\n")
        if file_content:
            prompt_text.append(f"Содержимое файла:\n---\n{parsed_file_content}\n---")
        response = self._client.chat(Chat(messages=[
            Messages(role=MessagesRole.SYSTEM, content=SYSTEM_PROMPT_CREATE_PLAN),
            Messages(role=MessagesRole.USER, content=''.join(prompt_text))
        ], temperature=0.2))
        data = json.loads(response.choices[0].message.content)
        if data.get("error"):
            raise ValueError(data["message"])
        return PlanGenerationResult(
            subject=data["subject"],
            grade=data["grade"],
            topic=data["topic"],
            stages=data["stages"]
        )

    def generate_handout(
            self,
            subject: str,
            grade: str,
            topic: str,
            description: str
    ) -> HandoutGenerationResult:
        response = self._client.chat(Chat(messages=[
            Messages(role=MessagesRole.SYSTEM, content=SYSTEM_PROMPT_CREATE_HANDOUT),
            Messages(role=MessagesRole.USER, content=USER_PROMPT_CREATE_HANDOUT_TEMPLATE.format(
                subject=subject,
                grade=grade,
                topic=topic,
                description=description
            ))
        ]))
        content = response.choices[0].message.content
        return HandoutGenerationResult(content=content)

    def extract_file_content(self, file_content: str):
        if not file_content:
            return ""
        response = self._client.chat(Chat(messages=[
            Messages(role=MessagesRole.USER, content=SYSTEM_PROMPT_EXTRACT_CONTENT.format(file_content=file_content)),
        ], temperature=0.2))
        content = response.choices[0].message.content
        return content
