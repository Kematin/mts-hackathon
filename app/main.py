"""
main.py — точка входа бэкенда LocalScript.

Содержит:
- POST /generate  — синхронный REST endpoint согласно OpenAPI контракту
- WebSocket /ws   — асинхронный endpoint для фронтенда с живыми статусами
- GET /health     — мониторинг состояния сервисов

Агентский pipeline на каждый запрос:
    1. Генерация Lua-кода через Ollama (llm.py)
    2. Валидация каждого lua{...}lua сниппета через lua-sandbox
    3. При ошибке — автоматический retry через fixer (макс MAX_RETRIES раз)
    4. Возврат результата клиенту

WebSocket события (фронтенд слушает их):
    task_created  — задача принята, передаётся task_id
    status        — промежуточный статус (processing / validating)
    done          — успешная генерация, передаётся готовый код
    failed        — исчерпаны попытки, передаётся последний вариант кода + ошибка
    error         — критическая ошибка
"""

import asyncio
import json
import uuid
import os
import httpx
import logging

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from llm import generate, fix, check_ollama, OLLAMA_MODEL

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# URL валидатора — при локальном запуске localhost:8081, в Docker — http://lua-sandbox:8081/validate
VALIDATOR_URL = os.getenv("VALIDATOR_URL", "http://localhost:8081/validate")

# Максимальное количество попыток исправить код после неудачной валидации
MAX_RETRIES = 2

# Потом заменим на бд пока рофлим
tasks: dict[str, dict] = {}

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Выполняется при старте и остановке приложения.
    При старте проверяем доступность Ollama и наличие нужной модели.
    """
    ok = await check_ollama()
    if ok:
        logger.info("Ollama доступна и модель загружена")
    else:
        logger.warning("Ollama недоступна или модель не найдена — проверь конфиг")
    yield

app = FastAPI(title="LocalScript API", lifespan=lifespan)

# CORS разрешён для всех origins — фронтенд может быть на любом порту
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


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


async def validate_code(code: str) -> tuple[bool, str]:
    """
    Отправляет Lua-код в lua-sandbox валидатор на проверку.

    Валидатор выполняет два шага:
        1. Синтаксическая проверка через luac
        2. Исполнение с mock wf-окружением через lua

    Returns:
        (True, "")             — код валиден
        (False, "описание")    — код невалиден, описание ошибки

    При недоступности валидатора возвращает (True, "") —
    не блокируем генерацию если sandbox упал.
    """
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                VALIDATOR_URL,
                json={"code": code},
            )
            data = response.json()
            return data.get("ok", False), data.get("error", "")
    except Exception as e:
        logger.error(f"Валидатор недоступен: {e}")
        # Graceful degradation — пропускаем валидацию если sandbox недоступен
        return True, ""


def extract_lua_snippets(code_json: str) -> list[str]:
    """
    Извлекает все Lua-сниппеты из JSON-ответа модели.

    Модель возвращает JSON вида:
        {"key": "lua{<код>}lua", "key2": "lua{<код>}lua"}

    Функция извлекает только внутренний код между lua{ и }lua
    чтобы передать его в валидатор без обёртки.

    Returns:
        Список строк с Lua-кодом (без lua{...}lua обёртки)
    """
    snippets = []
    try:
        data = json.loads(code_json)
        for value in data.values():
            if isinstance(value, str) and value.startswith("lua{") and value.endswith("}lua"):
                # Вырезаем код между lua{ и }lua (4 символа с начала, 4 с конца)
                inner = value[4:-4]
                snippets.append(inner)
    except Exception:
        pass
    return snippets


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
    prompt = task["prompt"]
    context = task["context"]

    # --- Шаг 1: Генерация ---
    task["status"] = "processing"
    await send(ws, "status", {"status": "processing", "message": "Генерирую код..."})

    try:
        code = await generate(prompt, context)
    except Exception as e:
        task["status"] = "failed"
        task["error"] = str(e)
        await send(ws, "error", {"message": f"Ошибка генерации: {e}"})
        return

    task["attempts"] += 1
    logger.info(f"[{task['id']}] Сгенерирован код (попытка {task['attempts']}): {code[:100]}...")

    # --- Шаг 2: Валидация + Retry ---
    for attempt in range(MAX_RETRIES + 1):
        task["status"] = "validating"
        await send(ws, "status", {"status": "validating", "message": f"Валидирую код (попытка {attempt + 1})..."})

        snippets = extract_lua_snippets(code)

        if not snippets:
            # Модель вернула что-то не то — нет lua{...}lua в ответе
            error_msg = "Не удалось извлечь lua{...}lua сниппеты из ответа модели"
            logger.warning(f"[{task['id']}] {error_msg}")
        else:
            # Валидируем каждый сниппет по очереди, останавливаемся на первой ошибке
            all_ok = True
            error_msg = ""
            for snippet in snippets:
                ok, err = await validate_code(snippet)
                if not ok:
                    all_ok = False
                    error_msg = err
                    break

            if all_ok:
                # Все сниппеты прошли валидацию — отдаём результат
                task["status"] = "done"
                task["code"] = code
                await send(ws, "done", {"code": code})
                logger.info(f"[{task['id']}] Готово после {attempt + 1} попыток валидации")
                return

        # Валидация упала — пробуем починить если остались попытки
        if attempt < MAX_RETRIES:
            task["attempts"] += 1
            await send(ws, "status", {
                "status": "processing",
                "message": f"Исправляю ошибку: {error_msg[:100]}..."
            })
            logger.info(f"[{task['id']}] Retry {attempt + 1}: {error_msg}")

            try:
                # Передаём модели оригинальный промпт + сломанный код + текст ошибки
                code = await fix(prompt, code, error_msg)
            except Exception as e:
                task["status"] = "failed"
                task["error"] = str(e)
                await send(ws, "error", {"message": f"Ошибка при исправлении: {e}"})
                return
        else:
            # Исчерпали все попытки — отдаём последний вариант с пометкой об ошибке
            task["status"] = "failed"
            task["error"] = error_msg
            await send(ws, "failed", {
                "code": code,
                "error": error_msg,
                "message": "Не удалось пройти валидацию, но вот последний вариант кода"
            })
            logger.warning(f"[{task['id']}] Исчерпаны попытки. Последняя ошибка: {error_msg}")
            return


from fastapi import HTTPException
from pydantic import BaseModel

class GenerateRequest(BaseModel):
    """Схема запроса для POST /generate согласно OpenAPI контракту."""
    prompt: str  # текст задачи на естественном языке (русский или английский)


#------------------------------------------
#ДЛЯ ФРОНТА
#------------------------------------------
@app.post("/generate")
async def generate_endpoint(request: GenerateRequest):
    """
    Синхронный endpoint генерации Lua-кода.

    Используется жюри и внешними интеграциями согласно OpenAPI контракту.
    Для фронтенда рекомендуется WebSocket /ws — он даёт живые статусы.

    Request:  {"prompt": "текст задачи"}
    Response: {"code": "{\"key\": \"lua{...}lua\"}"}
    """
    try:
        code = await generate(request.prompt)

        # Валидируем и при необходимости делаем одну попытку исправления
        snippets = extract_lua_snippets(code)
        for snippet in snippets:
            ok, error = await validate_code(snippet)
            if not ok:
                # Одна попытка исправить через fixer
                code = await fix(request.prompt, code, error)
                break

        return {"code": code}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    """
    WebSocket endpoint для фронтенда.

    Принимает сообщения вида:
        {"prompt": "текст задачи", "context": "опциональный JSON контекст wf.vars"}

    Отправляет события:
        {"event": "task_created", "task_id": "uuid"}
        {"event": "status", "status": "processing", "message": "..."}
        {"event": "status", "status": "validating", "message": "..."}
        {"event": "done", "code": "{...}"}
        {"event": "failed", "code": "{...}", "error": "...", "message": "..."}
        {"event": "error", "message": "..."}

    Соединение остаётся открытым — клиент может отправлять несколько задач подряд.
    """
    await ws.accept()
    logger.info("WebSocket подключён")

    try:
        while True:
            raw = await ws.receive_text()

            # Парсим входящее сообщение
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                await send(ws, "error", {"message": "Невалидный JSON"})
                continue

            prompt = data.get("prompt", "").strip()
            context = data.get("context")  # JSON строка с wf.vars контекстом, опционально

            if not prompt:
                await send(ws, "error", {"message": "Поле prompt обязательно"})
                continue

            # Создаём задачу и запускаем pipeline
            task = make_task(prompt, context)
            tasks[task["id"]] = task

            await send(ws, "task_created", {"task_id": task["id"]})
            logger.info(f"Создана задача {task['id']}: {prompt[:80]}")

            await run_pipeline(task, ws)

    except WebSocketDisconnect:
        logger.info("WebSocket отключён")
    except Exception as e:
        logger.error(f"WebSocket ошибка: {e}")
        try:
            await send(ws, "error", {"message": str(e)})
        except Exception:
            pass
#------------------------------------------
#ВСЕ
#------------------------------------------


# Рофлофункция для мониторинга состояния системы
@app.get("/health")
async def health():
    """
    Проверка состояния сервисов.

    Response:
        {
            "status": "ok",
            "ollama": true/false,       — доступна ли Ollama и загружена ли модель
            "tasks_in_memory": 42       — количество задач в памяти
        }
    """
    ollama_ok = await check_ollama()
    return {
        "status": "ok",
        "ollama": ollama_ok,
        "tasks_in_memory": len(tasks),
    }