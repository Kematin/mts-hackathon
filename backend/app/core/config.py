from pathlib import Path
from typing import List, Optional

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent.parent


def get_model_config(env_dir: str = f"{BASE_DIR}/.env"):
    config = SettingsConfigDict(
        env_file=env_dir, env_file_encoding="utf-8", extra="ignore"
    )
    return config


class AiSettings(BaseSettings):
    """Настройки ИИ

    ollama_url:
        при локальном запуске localhost:11434, в Docker — http://ollama:11434
    ollama_mode:
        Модель для генерации кода.
        Для разработки и дебага: qwen3.5:2b (быстрее, меньше VRAM)
        Для продакшена: qwen3.5:9b (лучше качество кода)
    validator_url:
        URL валидатора — при локальном запуске localhost:8081,
        в Docker — http://lua-sandbox:8081/validate
    max_validate_retries:
        Максимальное количество попыток исправить код после неудачной валидаци
    """

    ollama_url: str = Field(alias="OLLAMA_URL", default="http://localhost:11434")
    ollama_model: str = Field(alias="OLLAMA_MODEL", default="qwen3.5:2b")
    validator_url: str = Field(
        alias="VALIDATOR_URL", default="http://localhost:8081/validate"
    )
    max_validate_retries: int = Field(alias="MAX_RETRIES", default=2)

    model_config = get_model_config()


class Settings(BaseSettings):
    debug: bool = Field(alias="DEBUG", default=True)
    host: str = Field(alias="API_HOST", default="localhost")
    port: int = Field(alias="API_PORT", default=8000)

    _ai: Optional[AiSettings] = None

    @property
    def ai(self) -> AiSettings:
        if self._ai is None:
            self._ai = AiSettings()
        return self._ai

    model_config = get_model_config()


CONFIG = Settings()
