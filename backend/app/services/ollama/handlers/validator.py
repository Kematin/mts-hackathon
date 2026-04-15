from app.core.logger import get_logger
from app.services.ollama.api import OllamaApi
from app.services.ollama.handlers.base import Handler, PipelineContext

logger = get_logger(__name__)


class ValidatorHandler(Handler):
    def __init__(self, api: OllamaApi):
        super().__init__()
        self.api = api

    async def process(self, context: PipelineContext) -> PipelineContext:
        for snippet in context.snippets:
            try:
                ok, error = await self.api.get_validate_status(snippet.content)
            except Exception as e:
                logger.error(f"Валидатор недоступен: {e}")
                ok, error = True, ""

            if not ok:
                logger.warning(f"Ошибка валидации [{snippet.content[:50]}]: {error}")
                snippet.validation_error = error
                snippet.is_valid = False

        return context
