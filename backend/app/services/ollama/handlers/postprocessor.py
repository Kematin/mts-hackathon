from app.core.logger import get_logger
from app.services.ollama.handlers.base import Handler, PipelineContext

logger = get_logger(__name__)

FORBIDDEN = ["$.", "JsonPath", "require(", "os.time", "os.date", "io.", "_utils.array.sum", "_utils.array.sort"]

class PostprocessorHandler(Handler):
    async def process(self, context: PipelineContext) -> PipelineContext:
        """
        Проверяет ответ модели до отправки в валидатор.
        Если ответ явно кривой — помечает сниппет невалидным сразу.
        """
        for snippet in context.snippets:
            code = snippet.content

            if not code or not code.strip():
                snippet.is_valid = False
                snippet.validation_error = "Пустой код"
                continue

            if "return" not in code:
                snippet.is_valid = False
                snippet.validation_error = "Отсутствует return в коде"
                continue

            for f in FORBIDDEN:
                if f in code:
                    snippet.is_valid = False
                    snippet.validation_error = f"Запрещённая конструкция: {f}"
                    break

        return context