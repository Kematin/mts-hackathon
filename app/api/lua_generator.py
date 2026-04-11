import json

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect

from app.core.logger import get_logger
from app.schemas import GenerateRequest
from app.services.generator import (
    run_pipeline,
    send,
)
from app.services.ollama.get_service import get_ollama_service
from app.services.ollama.ollama_service import OllamaService
from app.services.tasks.base_task_service import BaseTaskService
from app.services.tasks.get_service import get_task_service

logger = get_logger(__name__)


router = APIRouter(prefix="", tags=["Lua Generate"])


@router.post("/generate")
async def generate_endpoint(
    request: GenerateRequest,
    ollama_service: OllamaService = Depends(get_ollama_service),
):
    """
    Синхронный endpoint генерации Lua-кода.

    Используется жюри и внешними интеграциями согласно OpenAPI контракту.
    Для фронтенда рекомендуется WebSocket /ws — он даёт живые статусы.

    Request:  {"prompt": "текст задачи"}
    Response: {"code": "{\"key\": \"lua{...}lua\"}"}
    """
    try:
        code = await ollama_service.generate_code(request.prompt)
        snippets = ollama_service.formatter.extract_lua_snippets(code)
        code = await ollama_service.validate_code(request, code, snippets)
        return {"code": code}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def health(
    ollama_service: OllamaService = Depends(get_ollama_service),
    task_service: BaseTaskService = Depends(get_task_service),
):
    """
    Проверка состояния сервисов.

    Response:
        {
            "status": "ok",
            "ollama": true/false,       — доступна ли Ollama и загружена ли модель
            "tasks_in_memory": 42       — количество задач в памяти
        }
    """
    ollama_ok = await ollama_service.check_ollama()
    return {
        "status": "ok",
        "ollama": ollama_ok,
        "tasks_in_memory": task_service.get_task_count(),
    }


@router.websocket("/ws")
async def websocket_endpoint(
    ws: WebSocket, task_service: BaseTaskService = Depends(get_task_service)
):
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
            task = task_service.make_task(prompt, context)

            await send(ws, "task_created", {"task_id": task.id})
            logger.info(f"Создана задача {task.id}: {prompt[:80]}")

            await run_pipeline(task, ws, task_service)

    except WebSocketDisconnect:
        logger.info("WebSocket отключён")
    except Exception as e:
        logger.error(f"WebSocket ошибка: {e}")
        try:
            await send(ws, "error", {"message": str(e)})
        except Exception:
            pass
