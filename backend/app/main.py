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

from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import api_v1_router
from app.core.config import CONFIG
from app.core.logger import get_logger, setup_logging
from app.services import get_ollama_service

setup_logging(debug=CONFIG.debug)
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Выполняется при старте и остановке приложения.
    При старте проверяем доступность Ollama и наличие нужной модели.
    """
    ollama_service = get_ollama_service()
    ok = await ollama_service.check_ollama()
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
app.include_router(api_v1_router)


if __name__ == "__main__":
    uvicorn.run("app:app", host=CONFIG.host, port=CONFIG.port, reload=CONFIG.debug)
