from typing import Type

from app.core.config import CONFIG
from app.core.constant import RETRY_SYSTEM_PROMPT, SYSTEM_PROMPT
from app.core.logger import get_logger
from app.schemas import GenerateRequest
from app.services.ollama.api import OllamaApi
from app.services.ollama.formatter import OllamaFormatter

logger = get_logger(__name__)


class OllamaService:
    formatter: Type[OllamaFormatter] = OllamaFormatter

    def __init__(self, ollama_api: OllamaApi):
        self.api: OllamaApi = ollama_api

    async def generate_code(self, user_prompt: str, context: str | None = None, history: list[dict] = []) -> str:
        user_message = user_prompt
        if context:
            user_message = f"{user_prompt}\n\nКонтекст:\n{context}"

        raw_answer = await self.api.create_chat_message(SYSTEM_PROMPT, user_message, history)
        return self.formatter.extract_json(raw_answer)

    async def fix_code(self, user_prompt: str, broken_code: str, error: str, history: list[dict] = []) -> str:
        user_message = (
            f"Исходный запрос пользователя: {user_prompt}\n\n"
            f"Код с ошибкой:\n{broken_code}\n\n"
            f"Ошибка валидации:\n{error}\n\n"
            f"Исправь код и верни валидный JSON."
        )

        raw_answer = await self.api.create_chat_message(RETRY_SYSTEM_PROMPT, user_message, history)
        return self.formatter.extract_json(raw_answer)

    async def check_ollama(self) -> bool:
        """
        Проверяет доступность Ollama и наличие нужной модели.

        Вызывается при старте приложения (lifespan в main.py).

        Returns:
            True  — Ollama доступна и OLLAMA_MODEL найдена в списке моделей
            False — Ollama недоступна или модель не загружена
        """
        available = await self.api.get_avaliable_models()
        return any(CONFIG.ai.ollama_model in m for m in available)

    async def validate_code(
        self, request: GenerateRequest, code: str, snippets: list[str]
    ) -> str:
        # ! Переписать функцию.
        # ! На данный момент просто перезаписывает последний полученный code
        # ! Использовать BaseModel схемы
        for snippet in snippets:
            try:
                ok, error = await self.api.get_validate_status(snippet)
            except Exception as e:
                # Graceful degradation — пропускаем валидацию если sandbox недоступен
                logger.error(f"Валидатор недоступен: {e}")
                ok, error = True, ""

            if not ok:
                code = await self.fix_code(request.prompt, code, error)
                break

        return code
