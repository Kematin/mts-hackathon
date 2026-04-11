from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect

from app.core.logger import get_logger
from app.enums import WebSocketEventStatus
from app.schemas import GenerateRequest
from app.services import get_ollama_service, get_task_service, get_websocket_service
from app.services.ollama.ollama_service import OllamaService
from app.services.tasks.base_task_service import BaseTaskService

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
        return await ollama_service.run_pipeline(request)

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

    ws_service = get_websocket_service(ws)

    try:
        while True:
            raw = await ws.receive_text()
            data = await ws_service.validate_data(raw)

            if not data:
                continue

            task = ws_service.task_service.make_task(data.prompt, data.context)

            await ws_service.send(
                WebSocketEventStatus.task_created, {"task_id": task.id}
            )
            logger.info(f"Создана задача {task.id}: {data.prompt[:80]}")

            await ws_service.run_pipeline(task)

    except WebSocketDisconnect:
        logger.info("WebSocket отключён")
    except Exception as e:
        logger.error(f"WebSocket ошибка: {e}")
        try:
            await ws_service.send(WebSocketEventStatus.error, {"message": str(e)})
        except Exception:
            pass
