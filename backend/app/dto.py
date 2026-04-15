from dataclasses import dataclass, field
from typing import Optional

from app.schemas import Code


@dataclass
class PipelineContext:
    prompt: str
    prompt_context: Optional[str] = None
    history: list[dict] = field(default_factory=list)
    raw_json: str = ""
    snippets: list[Code] = field(default_factory=list)
