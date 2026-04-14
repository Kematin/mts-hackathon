import json
from typing import Optional

from fastapi import WebSocket

from app.core.config import CONFIG
from app.core.logger import get_logger
from app.enums import CodeTaskStatus, WebSocketEventStatus
from app.schemas import CodeTask, WebSocketCodeData
from app.services.ollama.ollama_service import OllamaService
from app.services.tasks.base_task_service import BaseTaskService
from app.services.tasks.get_service import get_task_provider

logger = get_logger(__name__)

MAX_HISTORY = 6

class WebSocketService:
    def __init__(
        self,
        ws: WebSocket,
        ollama_service: OllamaService,
        task_service: BaseTaskService,
    ):
        self.ollama_service = ollama_service
        self.task_service = task_service
        self.ws = ws

    async def send(self, event: WebSocketEventStatus, data: dict):
        await self.ws.send_text(
            json.dumps({"event": event.value, **data}, ensure_ascii=False)
        )

    async def validate_data(self, raw: str) -> Optional[WebSocketCodeData]:
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            await self.send(WebSocketEventStatus.error, {"message": "Невалидный JSON"})
            return None

        prompt = data.get("prompt", "").strip()
        context = data.get("context")

        if not prompt:
            await self.send(
                WebSocketEventStatus.error, {"message": "Поле prompt обязательно"}
            )
            return None

        return WebSocketCodeData(prompt=prompt, context=context)

    def _trim_history(self, history: list[dict]) -> list[dict]:
        if len(history) <= MAX_HISTORY:
            return history
        return history[-MAX_HISTORY:]

    async def run_pipeline(self, task: CodeTask):
        self.task_service.set_provider(get_task_provider(task))

        # --- Шаг 0: Clarifier — нужно ли уточнение? ---
        # Пропускаем если: пользователь уже ответил на вопрос ИЛИ передан контекст wf.vars
        if not task.skip_clarification and not task.context:
            clarification = await self.ollama_service.clarify(task.prompt, task.context)

            if clarification["need_clarification"]:
                await self.send(
                    WebSocketEventStatus.clarification,
                    {"question": clarification["question"]}
                )
                task.history.append({"role": "assistant", "content": clarification["question"]})
                logger.info(f"[{task.id}] Clarifier задал вопрос: {clarification['question']}")
                return

        history = self._trim_history(task.history)

        # --- Шаг 1: Генерация ---
        self.task_service.provider.change_status(CodeTaskStatus.processing)
        await self.send(
            WebSocketEventStatus.status,
            {"status": CodeTaskStatus.processing.value, "message": "Генерирую код..."},
        )

        try:
            code = await self.ollama_service.generate_code(
                task.prompt, task.context, history
            )
        except Exception as e:
            self.task_service.provider.change_status(CodeTaskStatus.failed)
            self.task_service.provider.set_error(str(e))
            await self.send(
                WebSocketEventStatus.error, {"message": f"Ошибка генерации: {e}"}
            )
            return

        self.task_service.provider.increase_attempts(1)
        logger.info(
            f"[{task.id}] Сгенерирован код (попытка {task.attempts}): {code[:100]}..."
        )

        # --- Шаг 2: Валидация + Retry ---
        for attempt in range(CONFIG.ai.max_validate_retries + 1):
            self.task_service.provider.change_status(CodeTaskStatus.validating)
            await self.send(
                WebSocketEventStatus.status,
                {
                    "status": CodeTaskStatus.validating.value,
                    "message": f"Валидирую код (попытка {attempt + 1})...",
                },
            )

            snippets = self.ollama_service.formatter.extract_lua_snippets(code)

            if not snippets:
                error_msg = "Не удалось извлечь lua{...}lua сниппеты из ответа модели"
                logger.warning(f"[{task.id}] {error_msg}")
            else:
                all_ok = True
                error_msg = ""
                for snippet in snippets:
                    ok, err = await self.ollama_service.api.get_validate_status(
                        snippet.content
                    )
                    if not ok:
                        all_ok = False
                        error_msg = err
                        break

                if all_ok:
                    self.task_service.provider.change_status(CodeTaskStatus.done)
                    self.task_service.provider.set_code(code)
                    await self.send(WebSocketEventStatus.done, {"code": code})
                    logger.info(f"[{task.id}] Готово после {attempt + 1} попыток валидации")

                    task.history.append({"role": "user", "content": task.prompt})
                    task.history.append({"role": "assistant", "content": code})
                    logger.info(f"[{task.id}] История диалога: {len(task.history)} сообщений")
                    return

            if attempt < CONFIG.ai.max_validate_retries:
                self.task_service.provider.increase_attempts(1)
                self.task_service.provider.change_status(CodeTaskStatus.processing)
                await self.send(
                    WebSocketEventStatus.status,
                    {
                        "status": CodeTaskStatus.processing.value,
                        "message": f"Исправляю ошибку: {error_msg[:100]}...",
                    },
                )
                logger.info(f"[{task.id}] Retry {attempt + 1}: {error_msg}")

                try:
                    code = await self.ollama_service.fix_code(
                        task.prompt, code, error_msg, history
                    )
                except Exception as e:
                    self.task_service.provider.change_status(CodeTaskStatus.failed)
                    self.task_service.provider.set_error(str(e))
                    await self.send(
                        WebSocketEventStatus.error,
                        {"message": f"Ошибка при исправлении: {e}"},
                    )
                    return
            else:
                self.task_service.provider.change_status(CodeTaskStatus.failed)
                self.task_service.provider.set_error(error_msg)
                await self.send(
                    WebSocketEventStatus.failed,
                    {
                        "code": code,
                        "error": error_msg,
                        "message": "Не удалось пройти валидацию, но вот последний вариант кода",
                    },
                )
                logger.warning(f"[{task.id}] Исчерпаны попытки. Последняя ошибка: {error_msg}")
                return