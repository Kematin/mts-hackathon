from typing import Optional
from dataclasses import dataclass

from pydantic import BaseModel

from app.enums import CodeTaskStatus


@dataclass
class GenerateRequest(BaseModel):
    """Схема запроса для POST /generate согласно OpenAPI контракту."""

    prompt: str


@dataclass
class CodeTask(BaseModel):
    id: str
    prompt: str
    status: CodeTaskStatus
    attempts: int = 0
    code: Optional[str] = None
    error: Optional[str] = None
    context: Optional[str] = None
    history: list[dict] = []
    skip_clarification: bool = False


@dataclass
class Code(BaseModel):
    content: str
    is_valid: bool = True
    validation_error: Optional[str] = None


@dataclass
class WebSocketCodeData(BaseModel):
    prompt: str
    context: Optional[str] = None
