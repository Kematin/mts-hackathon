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
        """
        Отправляет JSON-событие в WebSocket.

        Формат сообщения: {"event": "<название>", ...доп. поля из data}

        Пример: {"event": "done", "code": "{\"result\": \"lua{...}lua\"}"}
        """
        await self.ws.send_text(json.dumps({"event": event.value, **data}))

    async def validate_data(self, raw: str) -> Optional[WebSocketCodeData]:
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            await self.send(WebSocketEventStatus.error, {"message": "Невалидный JSON"})
            return None

        prompt = data.get("prompt", "").strip()
        context = data.get("context")  # JSON строка с wf.vars контекстом, опционально

        if not prompt:
            await self.send(
                WebSocketEventStatus.error, {"message": "Поле prompt обязательно"}
            )
            return None

        return WebSocketCodeData(prompt=prompt, context=context)

    async def run_pipeline(self, task: CodeTask):
        """
        Основной агентский pipeline генерации и валидации Lua-кода.

        Шаги:
            1. Генерация — отправляем промпт в Ollama, получаем JSON с lua{...}lua
            2. Валидация — извлекаем сниппеты, проверяем каждый в lua-sandbox
            3. Retry     — если валидация упала, передаём код + ошибку в fixer LLM
            4. Результат — отправляем done или failed через WebSocket

        Args:
            task: объект задачи из хранилища tasks
        """
        self.task_service.set_provider(get_task_provider(task))

        # --- Шаг 1: Генерация ---
        self.task_service.provider.change_status(CodeTaskStatus.processing)
        await self.send(
            WebSocketEventStatus.status,
            {"status": CodeTaskStatus.processing.value, "message": "Генерирую код..."},
        )

        try:
            code = await self.ollama_service.generate_code(task.prompt, task.context)
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
                # Модель вернула что-то не то — нет lua{...}lua в ответе
                error_msg = "Не удалось извлечь lua{...}lua сниппеты из ответа модели"
                logger.warning(f"[{task.id}] {error_msg}")
            else:
                # Валидируем каждый сниппет по очереди, останавливаемся на первой ошибке
                all_ok = True
                error_msg = ""
                for snippet in snippets:
                    ok, err = await self.ollama_service.api.get_validate_status(snippet)
                    if not ok:
                        all_ok = False
                        error_msg = err
                        break

                if all_ok:
                    # Все сниппеты прошли валидацию — отдаём результат
                    self.task_service.provider.change_status(CodeTaskStatus.done)
                    self.task_service.provider.set_code(code)
                    await self.send(WebSocketEventStatus.done, {"code": code})
                    logger.info(
                        f"[{task.id}] Готово после {attempt + 1} попыток валидации"
                    )
                    return

            # Валидация упала — пробуем починить если остались попытки
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
                    # Передаём модели оригинальный промпт + сломанный код + текст ошибки
                    code = await self.ollama_service.fix_code(
                        task.prompt, code, error_msg
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
                # Исчерпали все попытки — отдаём последний вариант с пометкой об ошибке
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
                logger.warning(
                    f"[{task.id}] Исчерпаны попытки. Последняя ошибка: {error_msg}"
                )
                return
