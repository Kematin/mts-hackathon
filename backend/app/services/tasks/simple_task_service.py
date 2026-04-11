from typing import Dict
from uuid import uuid4

from app.enums import CodeTaskStatus
from app.schemas import CodeTask
from app.services.tasks.base_task_service import BaseTaskProvider, BaseTaskService


class SimpleTaskProvider(BaseTaskProvider):
    def change_status(self, status: CodeTaskStatus) -> None:
        self.current_task.status = status

    def increase_attempts(self, increase_value: int) -> None:
        self.current_task.attempts += increase_value

    def set_code(self, code: str) -> None:
        self.current_task.code = code

    def set_error(self, error: str) -> None:
        self.current_task.error = error


class SimpleTaskService(BaseTaskService):
    def __init__(self):
        self._tasks: Dict[str, CodeTask] = {}

    def add_task(self, task: CodeTask):
        self._tasks[task.id] = task

    def make_task(self, prompt, context=None):
        """
        Создаёт новый объект задачи с уникальным ID
        и добавляет его в словарь тасок.

        Статусы задачи:
            pending     — задача создана, ещё не начата
            processing  — идёт генерация или исправление кода
            validating  — код отправлен в lua-sandbox на проверку
            done        — код прошёл валидацию
            failed      — исчерпаны попытки или критическая ошибка
        """
        new_task = CodeTask(
            id=str(uuid4()),
            prompt=prompt,
            context=context,
            status=CodeTaskStatus.pending,
        )
        self.add_task(new_task)
        return new_task

    def get_task_count(self):
        return len(self._tasks)

    def set_provider(self, provider: SimpleTaskProvider):
        self.provider = provider
