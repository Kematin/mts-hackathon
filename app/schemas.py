from typing import Optional

from pydantic import BaseModel

from app.enums import CodeTaskStatus


class GenerateRequest(BaseModel):
    """Схема запроса для POST /generate согласно OpenAPI контракту."""

    prompt: str


class CodeTask(BaseModel):
    id: str
    prompt: str
    status: CodeTaskStatus
    attempts: int = 0
    code: Optional[str] = None
    error: Optional[str] = None
    context: Optional[str] = None
    history: list[dict] = [] #КОНТЕКСТ ЧАТА


class WebSocketCodeData(BaseModel):
    prompt: str
    context: Optional[str] = None
