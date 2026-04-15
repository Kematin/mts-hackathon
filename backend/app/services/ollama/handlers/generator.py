from app.core.constant import SYSTEM_PROMPT
from app.services.ollama.api import OllamaApi
from app.services.ollama.formatter import OllamaFormatter
from app.services.ollama.handlers.base import Handler, PipelineContext


class GeneratorHandler(Handler):
    def __init__(self, api: OllamaApi):
        super().__init__()
        self.api = api

    async def process(self, context: PipelineContext) -> PipelineContext:
        user_message = context.prompt
        if context.prompt_context:
            user_message = f"{context.prompt}\n\nКонтекст:\n{context.prompt_context}"

        raw_answer = await self.api.create_chat_message(
            SYSTEM_PROMPT, user_message, context.history
        )
        context.raw_json = OllamaFormatter.extract_json(raw_answer)
        context.snippets = OllamaFormatter.extract_lua_snippets(context.raw_json)

        return context
