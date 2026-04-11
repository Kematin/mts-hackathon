import json
from typing import Any, Optional, Type

from pydantic import BaseModel, TypeAdapter

from app.core.config import CONFIG
from app.core.constant import OLLAMA_OPTIONS
from app.core.logger import get_logger
from app.services.ollama.client import OllamaAsyncClient

logger = get_logger(__name__)


class OllamaApi:
    def __init__(self, client: OllamaAsyncClient):
        self.client: OllamaAsyncClient = client

    async def request(
        self,
        method: str,
        endpoint: str,
        *,
        request_model: Optional[BaseModel] = None,
        response_model: Optional[Type[BaseModel] | Type[list[BaseModel]]] = None,
        **kwargs: Any,
    ) -> Any:
        if request_model is not None:
            kwargs["json"] = request_model.model_dump(exclude_none=True)

        try:
            response = await self.client.request(method, endpoint, **kwargs)
        except Exception as e:
            logger.error(f"HTTP request failed: {e}")
            raise

        response_json = response.json()

        if response.status_code >= 400:
            try:
                logger.error(f"API Error(s): {response_json}")
            except Exception as e:
                logger.error(f"Error processing error response: {e}")
                response.raise_for_status()
            return

        if response_model is not None:
            return self._parse_response(response_json, response_model)
        return response_json

    @staticmethod
    def _parse_response(
        response_json: Any, response_model: Type[BaseModel] | Type[list[BaseModel]]
    ) -> Any:
        try:
            json_str = json.dumps(response_json)
            type_adapter = TypeAdapter(response_model)
            return type_adapter.validate_json(json_str)
        except Exception as e:
            logger.error(f"Error parsing response into model {response_model}: {e}")
            raise

    async def create_chat_message(self, system: str, user: str) -> str:
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
            "model": CONFIG.ai.ollama_model,
            "stream": False,
            "options": OLLAMA_OPTIONS,
            "format": {
                "type": "object",
                "additionalProperties": {
                    "type": "string"
                }
            },
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": "/no_think\n\n" + user},
            ],
        }

        data = await self.request("POST", "/api/chat", json=payload)
        return data["message"]["content"].strip()
    

    async def get_avaliable_models(self) -> list[str]:
        """
        Вызов Ollama /api/tags

        Получаем в ответе список доступных моделей Ollama.
        Нужна для проверки доступности модели OLLAMA_MODEL из конфига

        Returns:
            list[str] - список доступных моделей
        """

        data = await self.request("GET", "/api/tags")
        models = data.get("models", [])
        return [m["name"] for m in models]

    async def get_validate_status(self, code: str) -> tuple[bool, str]:
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
        response = await self.client.request(
            "POST",
            CONFIG.ai.validator_url,
            json={"code": code},
        )
        data = response.json()
        return data.get("ok", False), data.get("error", "")
