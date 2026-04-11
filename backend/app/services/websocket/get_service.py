from fastapi import WebSocket

from app.services.ollama.get_service import get_ollama_service
from app.services.tasks.get_service import get_task_service
from app.services.websocket.websocket_service import WebSocketService


def get_websocket_service(ws: WebSocket) -> WebSocketService:
    return WebSocketService(
        ws=ws,
        ollama_service=get_ollama_service(),
        task_service=get_task_service(),
    )
