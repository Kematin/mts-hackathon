from app.core.constant import RETRY_SYSTEM_PROMPT
from app.core.logger import get_logger
from app.schemas import Code
from app.services.ollama.api import OllamaApi
from app.services.ollama.formatter import OllamaFormatter
from app.services.ollama.handlers.base import Handler, PipelineContext

logger = get_logger(__name__)


class FixerHandler(Handler):
    def __init__(self, api: OllamaApi):
        super().__init__()
        self.api = api

    async def _fix(self, snippet: Code, context: PipelineContext) -> str:
        logger.debug(f"Fix broken code: {snippet.content}")
        user_message = (
            f"Исходный запрос пользователя: {context.prompt}\n\n"
            f"Код с ошибкой:\n{snippet.content}\n\n"
            f"Ошибка валидации:\n{snippet.validation_error}\n\n"
            f"Исправь код и верни валидный JSON."
        )
        raw_answer = await self.api.create_chat_message(
            RETRY_SYSTEM_PROMPT, user_message, context.history
        )
        snippet.content = OllamaFormatter.extract_json(raw_answer)
        
    async def process(self, context: PipelineContext) -> PipelineContext:
        for snippet in context.snippets:
            if not snippet.is_valid:
                await self._fix(snippet, context)

        return context
