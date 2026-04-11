import json

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect

from app.core.logger import get_logger
from app.schemas import GenerateRequest
from app.services.generator import (
    extract_lua_snippets,
    make_task,
    run_pipeline,
    send,
    validate_code,
)
from app.services.llm import check_ollama, fix, generate

logger = get_logger(__name__)

# Потом заменим на бд пока рофлим
tasks: dict[str, dict] = {}


router = APIRouter(prefix="", tags=["Lua Generate"])


# ------------------------------------------
# ДЛЯ ФРОНТА
# ------------------------------------------
@router.post("/generate")
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


@router.websocket("/ws")
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
            context = data.get(
                "context"
            )  # JSON строка с wf.vars контекстом, опционально

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


# ------------------------------------------
# ВСЕ
# ------------------------------------------


# Рофлофункция для мониторинга состояния системы
@router.get("/health")
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
