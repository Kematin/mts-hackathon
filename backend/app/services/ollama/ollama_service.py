import json
from typing import Type

from app.core.config import CONFIG
from app.core.constant import (
    CLARIFIER_SYSTEM_PROMPT,
    RETRY_SYSTEM_PROMPT,
    SYSTEM_PROMPT,
)
from app.core.logger import get_logger
from app.schemas import Code, GenerateRequest
from app.services.ollama.api import OllamaApi
from app.services.ollama.formatter import OllamaFormatter

logger = get_logger(__name__)


class OllamaService:
    formatter: Type[OllamaFormatter] = OllamaFormatter

    def __init__(self, ollama_api: OllamaApi):
        self.api: OllamaApi = ollama_api

    async def run_pipeline(self, request: GenerateRequest) -> list[Code]:
        raw_json_code = await self.generate_code(request.prompt)
        snippets = self.formatter.extract_lua_snippets(raw_json_code)
        validated_snippets = await self.validate_and_fix_code(request.prompt, snippets)
        return validated_snippets

    async def generate_code(
        self, user_prompt: str, context: str | None = None, history: list[dict] = []
    ) -> str:
        user_message = user_prompt
        if context:
            user_message = f"{user_prompt}\n\nКонтекст:\n{context}"

        raw_answer = await self.api.create_chat_message(
            SYSTEM_PROMPT, user_message, history
        )
        return self.formatter.extract_json(raw_answer)

    async def fix_code(
        self, user_prompt: str, broken_code: str, error: str, history: list[dict] = []
    ) -> str:
        user_message = (
            f"Исходный запрос пользователя: {user_prompt}\n\n"
            f"Код с ошибкой:\n{broken_code}\n\n"
            f"Ошибка валидации:\n{error}\n\n"
            f"Исправь код и верни валидный JSON."
        )

        raw_answer = await self.api.create_chat_message(
            RETRY_SYSTEM_PROMPT, user_message, history
        )
        return self.formatter.extract_json(raw_answer)

    async def clarify(self, user_prompt: str, context: str | None = None) -> dict:
        """
        Проверяет нужно ли уточнение перед генерацией.

        Returns:
            {"need_clarification": True, "question": "вопрос"} — нужно уточнение
            {"need_clarification": False, "question": ""}      — можно генерировать
        """
        user_message = user_prompt
        if context:
            user_message = f"{user_prompt}\n\nКонтекст:\n{context}"

        try:
            raw = await self.api.create_chat_message(
                CLARIFIER_SYSTEM_PROMPT, user_message
            )
            result = self.formatter.extract_json(raw)
            data = json.loads(result)
            return {
                "need_clarification": bool(data.get("need_clarification", False)),
                "question": data.get("question", ""),
            }
        except Exception as e:
            logger.error(f"Clarifier ошибка: {e}")
            # При ошибке — не блокируем, просто генерируем
            return {"need_clarification": False, "question": ""}

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

    async def validate_and_fix_code(
        self, user_prompt: str, snippets: list[Code]
    ) -> list[Code]:
        for snippet in snippets:
            try:
                ok, error = await self.api.get_validate_status(snippet.content)
            except Exception as e:
                # Graceful degradation — пропускаем валидацию если sandbox недоступен
                logger.error(f"Валидатор недоступен: {e}")
                ok, error = True, ""

            if not ok:
                fixed_code = await self.fix_code(user_prompt, snippet.content, error)
                snippet.content = fixed_code

        logger.debug(snippets)
        return snippets
