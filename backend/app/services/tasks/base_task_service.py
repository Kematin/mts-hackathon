from abc import ABC, abstractmethod
from typing import Optional

from app.schemas import CodeTask, CodeTaskStatus


class BaseTaskProvider(ABC):
    def __init__(self, task: CodeTask):
        self.current_task = task

    @abstractmethod
    def change_status(self, status: CodeTaskStatus) -> None:
        pass

    @abstractmethod
    def increase_attempts(self, increase_value: int) -> None:
        pass

    @abstractmethod
    def set_code(self, code: str) -> None:
        pass

    @abstractmethod
    def set_error(self, error: str) -> None:
        pass


class BaseTaskService(ABC):
    provider: Optional[BaseTaskProvider] = None
    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    @abstractmethod
    def make_task(self, prompt: str, context: Optional[str] = None) -> CodeTask:
        pass

    @abstractmethod
    def get_task_count(self) -> int:
        pass

    @abstractmethod
    def set_provider(self, provider: BaseTaskProvider):
        self.provider = provider
