import json
import uuid

from fastapi import WebSocket

from app.core.config import CONFIG
from app.core.logger import get_logger
from app.services.ollama.get_service import get_ollama_service

logger = get_logger(__name__)

# Потом заменим на бд пока рофлим
tasks: dict[str, dict] = {}


def make_task(prompt: str, context: str | None) -> dict:
    """
    Создаёт новый объект задачи с уникальным ID.

    Статусы задачи:
        pending     — задача создана, ещё не начата
        processing  — идёт генерация или исправление кода
        validating  — код отправлен в lua-sandbox на проверку
        done        — код прошёл валидацию
        failed      — исчерпаны попытки или критическая ошибка
    """
    return {
        "id": str(uuid.uuid4()),
        "prompt": prompt,
        "context": context,
        "status": "pending",
        "code": None,
        "error": None,
        "attempts": 0,  # счётчик обращений к LLM (генерация + retry)
    }


async def send(ws: WebSocket, event: str, data: dict):
    """
    Отправляет JSON-событие в WebSocket.

    Формат сообщения: {"event": "<название>", ...доп. поля из data}

    Пример: {"event": "done", "code": "{\"result\": \"lua{...}lua\"}"}
    """
    await ws.send_text(json.dumps({"event": event, **data}))


async def run_pipeline(task: dict, ws: WebSocket):
    """
    Основной агентский pipeline генерации и валидации Lua-кода.

    Шаги:
        1. Генерация — отправляем промпт в Ollama, получаем JSON с lua{...}lua
        2. Валидация — извлекаем сниппеты, проверяем каждый в lua-sandbox
        3. Retry     — если валидация упала, передаём код + ошибку в fixer LLM
        4. Результат — отправляем done или failed через WebSocket

    Args:
        task: объект задачи из хранилища tasks
        ws:   WebSocket соединение с клиентом
    """
    ollama_service = get_ollama_service()

    prompt = task["prompt"]
    context = task["context"]

    # --- Шаг 1: Генерация ---
    task["status"] = "processing"
    await send(ws, "status", {"status": "processing", "message": "Генерирую код..."})

    try:
        code = await ollama_service.generate_code(prompt, context)
    except Exception as e:
        task["status"] = "failed"
        task["error"] = str(e)
        await send(ws, "error", {"message": f"Ошибка генерации: {e}"})
        return

    task["attempts"] += 1
    logger.info(
        f"[{task['id']}] Сгенерирован код (попытка {task['attempts']}): {code[:100]}..."
    )

    # --- Шаг 2: Валидация + Retry ---
    for attempt in range(CONFIG.ai.max_validate_retries + 1):
        task["status"] = "validating"
        await send(
            ws,
            "status",
            {
                "status": "validating",
                "message": f"Валидирую код (попытка {attempt + 1})...",
            },
        )

        snippets = ollama_service.formatter.extract_lua_snippets(code)

        if not snippets:
            # Модель вернула что-то не то — нет lua{...}lua в ответе
            error_msg = "Не удалось извлечь lua{...}lua сниппеты из ответа модели"
            logger.warning(f"[{task['id']}] {error_msg}")
        else:
            # Валидируем каждый сниппет по очереди, останавливаемся на первой ошибке
            all_ok = True
            error_msg = ""
            for snippet in snippets:
                ok, err = await ollama_service.api.get_validate_status(snippet)
                if not ok:
                    all_ok = False
                    error_msg = err
                    break

            if all_ok:
                # Все сниппеты прошли валидацию — отдаём результат
                task["status"] = "done"
                task["code"] = code
                await send(ws, "done", {"code": code})
                logger.info(
                    f"[{task['id']}] Готово после {attempt + 1} попыток валидации"
                )
                return

        # Валидация упала — пробуем починить если остались попытки
        if attempt < CONFIG.ai.max_validate_retries:
            task["attempts"] += 1
            await send(
                ws,
                "status",
                {
                    "status": "processing",
                    "message": f"Исправляю ошибку: {error_msg[:100]}...",
                },
            )
            logger.info(f"[{task['id']}] Retry {attempt + 1}: {error_msg}")

            try:
                # Передаём модели оригинальный промпт + сломанный код + текст ошибки
                code = await ollama_service.fix_code(prompt, code, error_msg)
            except Exception as e:
                task["status"] = "failed"
                task["error"] = str(e)
                await send(ws, "error", {"message": f"Ошибка при исправлении: {e}"})
                return
        else:
            # Исчерпали все попытки — отдаём последний вариант с пометкой об ошибке
            task["status"] = "failed"
            task["error"] = error_msg
            await send(
                ws,
                "failed",
                {
                    "code": code,
                    "error": error_msg,
                    "message": "Не удалось пройти валидацию, но вот последний вариант кода",
                },
            )
            logger.warning(
                f"[{task['id']}] Исчерпаны попытки. Последняя ошибка: {error_msg}"
            )
            return
