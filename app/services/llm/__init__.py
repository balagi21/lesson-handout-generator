from ...config import settings
from .gigachat import GigaChatProvider


llm_gigachat = GigaChatProvider(api_key=settings.gigachat_api_key)