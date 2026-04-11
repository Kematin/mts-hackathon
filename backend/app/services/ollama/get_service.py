"""
OllamaService — клиент для взаимодействия с локальной LLM через Ollama.

Содержит четыре публичных функции:
    generate_code()     - генерация Lua-кода по запросу пользователя
    fix_code()          - исправление кода после неудачной валидации
    check_ollama()      - проверка доступности Ollama и наличия модели
    validate_code()     - валидация полученного Lua-кода

Все запросы идут через Ollama REST API (/api/chat).
Никаких внешних AI-сервисов не используется.
"""

from app.services.ollama.api import OllamaApi
from app.services.ollama.client import get_ollama_async_client
from app.services.ollama.ollama_service import OllamaService


def get_ollama_service() -> OllamaService:
    api = OllamaApi(client=get_ollama_async_client())
    return OllamaService(ollama_api=api)
