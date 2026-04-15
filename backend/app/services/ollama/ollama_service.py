import json
from typing import Type

from fastapi import HTTPException, status

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
from app.services.ollama.handlers import (
    FixerHandler,
    GeneratorHandler,
    PostprocessorHandler,
    ValidatorHandler,
    PipelineContext,
)

logger = get_logger(__name__)


class OllamaService:
    formatter: Type[OllamaFormatter] = OllamaFormatter

    def __init__(self, ollama_api: OllamaApi):
        self.api: OllamaApi = ollama_api

    def _build_chain_pipeline(self) -> GeneratorHandler:
        generator = GeneratorHandler(self.api)
        postprocessor = PostprocessorHandler()
        validator = ValidatorHandler(self.api)
        fixer = FixerHandler(self.api)

        generator.set_next(postprocessor).set_next(validator).set_next(fixer)
        return generator

    async def run_pipeline(self, request: GenerateRequest) -> str:
        chain = self._build_chain_pipeline()
        context = PipelineContext(prompt=request.prompt)
        try:
            result = await chain.handle(context)
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e),
            )
        return result.raw_json

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
