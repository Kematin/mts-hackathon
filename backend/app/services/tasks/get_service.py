from app.schemas import CodeTask
from app.services.tasks.base_task_service import BaseTaskProvider, BaseTaskService
from app.services.tasks.simple_task_service import SimpleTaskProvider, SimpleTaskService


def get_task_service() -> BaseTaskService:
    return SimpleTaskService()


def get_task_provider(task: CodeTask) -> BaseTaskProvider:
    return SimpleTaskProvider(task)
