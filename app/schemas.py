from pydantic import BaseModel


class GenerateRequest(BaseModel):
    """Схема запроса для POST /generate согласно OpenAPI контракту."""

    prompt: str
