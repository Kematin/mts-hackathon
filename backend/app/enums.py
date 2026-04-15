from enum import Enum


class CodeTaskStatus(Enum):
    """
    Статусы задач по генерации кода:
        pending     — задача создана, ещё не начата
        processing  — идёт генерация или исправление кода
        validating  — код отправлен в lua-sandbox на проверку
        done        — код прошёл валидацию
        failed      — исчерпаны попытки или критическая ошибка
    """

    pending = "PENDING"
    processing = "PROCESSING"
    validating = "VALIDATING"
    done = "DONE"
    failed = "FAILED"


class WebSocketEventStatus(Enum):
    """
    События WebSocket /ws соединения:
        task_created — задача принята, передаётся task_id
        status       — промежуточный статус (processing / validating)
        done         — успешная генерация, передаётся готовый код
        failed       — исчерпаны попытки, передаётся последний вариант кода + ошибка
        error        — критическая ошибка
    """

    task_created = "TASK_CREATED"
    status = "STATUS"
    done = "DONE"
    failed = "FAILED"
    error = "ERROR"
    clarification = "CLARIFICATION"
