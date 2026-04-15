from abc import ABC, abstractmethod
from typing import Optional

from app.dto import PipelineContext


class Handler(ABC):
    def __init__(self):
        self.successor: Optional["Handler"] = None

    @abstractmethod
    async def process(self, context: PipelineContext) -> PipelineContext:
        pass

    async def handle(self, context: PipelineContext) -> PipelineContext:
        context = await self.process(context)
        if self.successor:
            return await self.successor.handle(context)
        return context

    def set_next(self, handler: "Handler") -> "Handler":
        self.successor = handler
        return handler
