import httpx

from app.core.config import CONFIG
from app.core.constant import OLLAMA_TIMEOUT


class OllamaAsyncClient(httpx.AsyncClient):
    access_token: str = ""
    token_expires_at: float = 0.0


def get_ollama_async_client(base_url: str = CONFIG.ai.ollama_url) -> OllamaAsyncClient:
    client = OllamaAsyncClient(
        base_url=base_url,
        timeout=httpx.Timeout(timeout=OLLAMA_TIMEOUT, connect=5.0),
        trust_env=False,
    )
    return client
