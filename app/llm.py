"""
llm.py — клиент для взаимодействия с локальной LLM через Ollama.

Содержит три публичных функции:
    generate()     — генерация Lua-кода по запросу пользователя
    fix()          — исправление кода после неудачной валидации
    check_ollama() — проверка доступности Ollama и наличия модели

Все запросы идут через Ollama REST API (/api/chat).
Никаких внешних AI-сервисов не используется.
"""

import os
import json
import httpx

from prompt import SYSTEM_PROMPT, RETRY_SYSTEM_PROMPT

# URL Ollama — при локальном запуске localhost:11434, в Docker — http://ollama:11434
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")

# Модель для генерации кода.
# Для разработки и дебага: qwen3.5:2b (быстрее, меньше VRAM)
# Для продакшена: qwen3.5:9b (лучше качество кода)
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen3.5:2b")

# Параметры генерации — фиксированы согласно требованиям хакатона.
# num_ctx=4096, num_predict фиксируется организаторами при проверке.
OLLAMA_OPTIONS = {
    "num_ctx": 4096,       # размер контекстного окна
    "num_predict": 512,    # максимальное количество токенов в ответе
    "temperature": 0.2,    # низкая температура = более детерминированные ответы
    "think": False,        # отключаем thinking mode у qwen3.5 — экономим токены
}

async def _chat(system: str, user: str) -> str:
    """
    Базовый вызов Ollama /api/chat.

    Отправляет system + user сообщения, возвращает сырой текст ответа модели.
    Префикс /no_think в user сообщении явно отключает thinking mode qwen3.5
    (дополнительная страховка помимо "think": False в options).

    Args:
        system: system prompt с правилами и few-shot примерами
        user:   запрос пользователя (опционально с контекстом wf.vars)

    Returns:
        Сырой текст ответа модели (может содержать markdown-обёртку)

    Raises:
        httpx.HTTPStatusError: если Ollama вернула ошибку
    """
    payload = {
        "model": OLLAMA_MODEL,
        "stream": False,          # получаем полный ответ сразу, не стримим
        "options": OLLAMA_OPTIONS,
        "messages": [
            {"role": "system", "content": system},
            # /no_think — директива для qwen3.5 пропустить этап размышлений
            {"role": "user", "content": "/no_think\n\n" + user},
        ],
    }

    # trust_env=False — игнорируем системные прокси (решает проблему с корпоративными сетями)
    async with httpx.AsyncClient(timeout=120.0, trust_env=False) as client:
        response = await client.post(
            f"{OLLAMA_URL}/api/chat",
            json=payload,
        )
        response.raise_for_status()
        data = response.json()
        return data["message"]["content"].strip()


def _extract_json(raw: str) -> str:
    """
    Извлекает чистый JSON из сырого ответа модели.

    Модель иногда оборачивает ответ в markdown-блок ```json ... ```
    несмотря на инструкции в промпте. Эта функция чистит обёртку.

    Алгоритм:
        1. Убираем строки начинающиеся с ``` 
        2. Ищем первый { и последний } — берём всё между ними

    Args:
        raw: сырой текст ответа модели

    Returns:
        Строка с валидным JSON

    Raises:
        ValueError: если JSON не найден в ответе
    """
    # Убираем markdown-блоки если модель всё же добавила их
    if "```" in raw:
        lines = raw.splitlines()
        filtered = [l for l in lines if not l.strip().startswith("```")]
        raw = "\n".join(filtered)

    # Ищем первый { и последний } — берём всё между ними
    start = raw.find("{")
    end = raw.rfind("}")
    if start == -1 or end == -1:
        raise ValueError(f"JSON не найден в ответе модели: {raw!r}")

    return raw[start : end + 1]

async def generate(user_prompt: str, context: str | None = None) -> str:
    """
    Генерирует Lua-код по запросу пользователя.

    Использует SYSTEM_PROMPT с правилами платформы MWS Octapi
    и всеми 8 примерами из публичной выборки (few-shot prompting).

    Args:
        user_prompt: задача на естественном языке (русский или английский)
        context:     опциональный JSON с wf.vars контекстом от пользователя
                     например: '{"wf": {"vars": {"emails": [...]}}}'

    Returns:
        JSON строка вида: '{"key": "lua{<код>}lua"}'
    """
    user_message = user_prompt
    if context:
        # Добавляем контекст к промпту чтобы модель знала структуру wf.vars
        user_message = f"{user_prompt}\n\nКонтекст:\n{context}"

    raw = await _chat(SYSTEM_PROMPT, user_message)
    return _extract_json(raw)


async def fix(user_prompt: str, broken_code: str, error: str) -> str:
    """
    Исправляет Lua-код который не прошёл валидацию.

    Вызывается из run_pipeline в main.py при неудачной валидации.
    Передаёт модели оригинальный запрос, сломанный код и текст ошибки.
    Использует отдельный RETRY_SYSTEM_PROMPT — короткий, без примеров.

    Args:
        user_prompt:  оригинальный запрос пользователя
        broken_code:  JSON строка с кодом который не прошёл валидацию
        error:        текст ошибки от lua-sandbox валидатора

    Returns:
        JSON строка с исправленным кодом
    """
    user_message = (
        f"Исходный запрос пользователя: {user_prompt}\n\n"
        f"Код с ошибкой:\n{broken_code}\n\n"
        f"Ошибка валидации:\n{error}\n\n"
        f"Исправь код и верни валидный JSON."
    )

    raw = await _chat(RETRY_SYSTEM_PROMPT, user_message)
    return _extract_json(raw)


async def check_ollama() -> bool:
    """
    Проверяет доступность Ollama и наличие нужной модели.

    Вызывается при старте приложения (lifespan в main.py).

    Returns:
        True  — Ollama доступна и OLLAMA_MODEL найдена в списке моделей
        False — Ollama недоступна или модель не загружена
    """
    try:
        async with httpx.AsyncClient(timeout=5.0, trust_env=False) as client:
            response = await client.get(f"{OLLAMA_URL}/api/tags")
            response.raise_for_status()
            models = response.json().get("models", [])
            available = [m["name"] for m in models]
            # Проверяем что OLLAMA_MODEL есть среди доступных моделей
            return any(OLLAMA_MODEL in m for m in available)
    except Exception:
        return False